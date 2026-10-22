import "@testing-library/jest-dom/vitest";
import { screen } from "@testing-library/react";
import { rawFileUrl, type NodeDetail } from "../../api/queries";
import { NodeView } from "../../app/NodeView";
import { renderInBase, resetApi, respond } from "../../testing";
import { openPdf } from "./pdfjs";

vi.mock("../../api/client", () => import("../../testing").then((m) => m.mockClient()));
vi.mock("./pdfjs", () => ({ openPdf: vi.fn() }));

const NODE_ID = "11111111-1111-1111-1111-111111111111";

function fileNode(title: string, mime: string, pages: number | null = null): NodeDetail {
  return {
    id: NODE_ID,
    kb_id: "kb-1",
    parent_id: "folder-1",
    kind: "file",
    title,
    deleted_at: null,
    path: `Bradesco/Residencial/${title}`,
    page: null,
    file: { size: 2_400_000, mime, pages, protected: false, sha256: "abc" },
    versions: 2,
  };
}

function renderFile(node: NodeDetail, search = "") {
  respond("GET", `/nodes/${NODE_ID}`, { body: node });
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
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("FileView", () => {
  it("opens a PDF with pdf.js at the page of ?p=", async () => {
    const getPage = fakePdf(180);
    renderFile(fileNode("Condições Gerais 2026.pdf", "application/pdf", 180), "?p=16");

    expect(await screen.findByRole("img", { name: "Página 16 do PDF" })).toBeInTheDocument();
    expect(openPdf).toHaveBeenCalledWith(rawFileUrl(NODE_ID), expect.any(Function));
    expect(getPage).toHaveBeenCalledWith(16);
    expect(screen.getByText("Bradesco / Residencial · 180 páginas · arquivo original")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Página" })).toHaveValue("16");
  });

  it("shows an image fitted on the desk, its URL changing with its content", async () => {
    renderFile(fileNode("Fachada.png", "image/png"));

    const image = await screen.findByRole("img", { name: "Fachada.png" });
    expect(image).toHaveAttribute("src", `${rawFileUrl(NODE_ID)}?v=abc`);
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

  it("Baixar points to the raw route", async () => {
    fakePdf(3);
    renderFile(fileNode("Condições Gerais 2026.pdf", "application/pdf", 3));

    const link = await screen.findByRole("link", { name: "Baixar" });
    expect(link).toHaveAttribute("href", rawFileUrl(NODE_ID));
  });
});
