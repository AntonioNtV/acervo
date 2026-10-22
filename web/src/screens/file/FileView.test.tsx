import "@testing-library/jest-dom/vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { NodeDetail } from "../../api/client";
import { calls, filePart, nodeFields, renderInBase, resetApi, respond } from "../../api/testing";
import { NodeView } from "../../app/NodeView";
import { openPdf } from "../../viewer/pdfjs";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));
vi.mock("../../viewer/pdfjs", () => ({ openPdf: vi.fn() }));

const NODE_ID = "11111111-1111-1111-1111-111111111111";
const RAW = `/v1/files/${NODE_ID}/raw`;

function fileNode(title: string, mime: string, pages: number | null = null): NodeDetail {
  return {
    ...nodeFields,
    id: NODE_ID,
    kb_id: "kb-1",
    parent_id: "folder-1",
    kind: "file",
    title,
    deleted_at: null,
    path: `Bradesco/Residencial/${title}`,
    page: null,
    file: filePart(NODE_ID, { size: 2_400_000, mime, pages, protected: false, sha256: "abc" }),
    versions: 2,
  };
}

function renderFile(node: NodeDetail, search = "") {
  respond("GET", `/v1/nodes/${NODE_ID}`, { body: node });
  return renderInBase(<NodeView />, `/kbs/kb-1/n/${NODE_ID}${search}`);
}

function fakePdf(numPages: number) {
  const getPage = vi.fn(async () => ({
    getViewport: () => ({ width: 600, height: 800 }),
    render: () => ({ promise: Promise.resolve(), cancel: () => {} }),
  }));
  vi.mocked(openPdf).mockReturnValue({
    promise: Promise.resolve({ numPages, getPage } as never),
    destroy: () => {},
  });
  return getPage;
}

beforeEach(() => {
  localStorage.clear();
  resetApi();
  vi.mocked(openPdf).mockReset();
  respond("GET", RAW, { body: "%PDF" });
  URL.createObjectURL = vi.fn(() => "blob:raw");
  URL.revokeObjectURL = vi.fn();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("FileView", () => {
  it("opens a PDF with pdf.js at the page of ?p=", async () => {
    const getPage = fakePdf(180);
    renderFile(fileNode("Condições Gerais 2026.pdf", "application/pdf", 180), "?p=16");

    expect(await screen.findByRole("img", { name: "Página 16 do PDF" })).toBeInTheDocument();
    expect(openPdf).toHaveBeenCalledWith({ url: RAW, httpHeaders: { "X-API-Key": "test-key" } }, expect.any(Function));
    expect(getPage).toHaveBeenCalledWith(16);
    expect(screen.getByText("Bradesco / Residencial · 180 páginas · arquivo original")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Página" })).toHaveValue("16");
  });

  it("shows an image fitted on the desk, its bytes fetched with the key", async () => {
    renderFile(fileNode("Fachada.png", "image/png"));

    const image = await screen.findByRole("img", { name: "Fachada.png" });
    expect(image).toHaveAttribute("src", "blob:raw");
    expect(calls.find((call) => call.path === RAW)?.key).toBe("test-key");
    expect(openPdf).not.toHaveBeenCalled();
  });

  it("shows any other file's type, size and versions", async () => {
    renderFile(fileNode("Tabela.xlsx", "application/vnd.ms-excel"));

    expect(await screen.findByText("application/vnd.ms-excel")).toBeInTheDocument();
    expect(screen.getByText("2,3 MB")).toBeInTheDocument();
    expect(screen.getByText("2 versões")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(openPdf).not.toHaveBeenCalled();
  });

  it("Baixar fetches the raw route with the key and saves it under the file's name", async () => {
    fakePdf(3);
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    renderFile(fileNode("Condições Gerais 2026.pdf", "application/pdf", 3));

    await userEvent.click(await screen.findByRole("button", { name: "Baixar" }));

    await waitFor(() => expect(click).toHaveBeenCalledTimes(1));
    const link = click.mock.contexts[0] as HTMLAnchorElement;
    expect(link.download).toBe("Condições Gerais 2026.pdf");
    expect(link.getAttribute("href")).toBe("blob:raw");
    expect(calls.find((call) => call.path === RAW)?.key).toBe("test-key");
  });
});
