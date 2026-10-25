import "@testing-library/jest-dom/vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { NodeDetail } from "../../api/client";
import { calls, nodeFields, renderInBase, resetApi, respond } from "../../api/testing";
import { NodeView } from "../../app/NodeView";
import { openPdf } from "../../viewer/pdfjs";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));
vi.mock("../../viewer/pdfjs", () => ({ openPdf: vi.fn() }));

const NODE_ID = "11111111-1111-1111-1111-111111111111";
const RAW = `/v1/files/${NODE_ID}/raw`;
const LINK = `/v1/files/${NODE_ID}/link`;
const SIGNED = `${RAW}?expires=1792000000&signature=abc`;

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
    file: { size: 2_400_000, mime, pages, protected: false, sha256: "abc" },
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
  // Built from the request's Host, so the API's own origin; the app keeps only the path.
  respond("POST", LINK, { body: { url: `http://localhost:8000${SIGNED}`, expires_at: "2026-10-22T10:01:00Z" } });
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
    // The page is asked for in an effect, which may run after the canvas is on screen.
    await waitFor(() => expect(getPage).toHaveBeenCalledWith(16));
    expect(screen.getByText("arquivo original · 180 páginas · 2,3 MB")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Página" })).toHaveValue("16");
  });

  it("shows an image fitted on the desk from a signed link", async () => {
    renderFile(fileNode("Fachada.png", "image/png"));

    const image = await screen.findByRole("img", { name: "Fachada.png" });
    expect(image).toHaveAttribute("src", SIGNED);
    expect(calls.find((call) => call.path === LINK)?.key).toBe("test-key");
    expect(calls.some((call) => call.path === RAW)).toBe(false);
    expect(openPdf).not.toHaveBeenCalled();
  });

  it("plays a video from a signed link", async () => {
    renderFile(fileNode("Vistoria.mp4", "video/mp4"));

    await screen.findByRole("button", { name: "Tocar" });
    expect(document.querySelector("video")).toHaveAttribute("src", SIGNED);
    expect(screen.getByRole("button", { name: "Baixar" })).toBeInTheDocument();
    expect(openPdf).not.toHaveBeenCalled();
  });

  it("plays an audio from a signed link", async () => {
    renderFile(fileNode("Reunião.m4a", "audio/mp4"));

    await screen.findByRole("button", { name: "Tocar" });
    expect(document.querySelector("audio")).toHaveAttribute("src", SIGNED);
    expect(document.querySelector("video")).not.toBeInTheDocument();
  });

  it("downloads an image from its toolbar", async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    renderFile(fileNode("Fachada.png", "image/png"));

    const toolbar = await screen.findByRole("toolbar");
    expect(within(toolbar).getByRole("button", { name: "Substituir" })).toBeInTheDocument();
    expect(within(toolbar).getByRole("button", { name: "Abrir" })).toBeInTheDocument();
    await userEvent.click(within(toolbar).getByRole("button", { name: "Baixar" }));

    await waitFor(() => expect(click).toHaveBeenCalledTimes(1));
    const link = click.mock.contexts[0] as HTMLAnchorElement;
    expect(link.download).toBe("Fachada.png");
    expect(link.getAttribute("href")).toBe(SIGNED);
  });

  it("shows a text instead of an image that does not load", async () => {
    renderFile(fileNode("Fachada.png", "image/png"));

    fireEvent.error(await screen.findByRole("img", { name: "Fachada.png" }));

    expect(await screen.findByText("Não foi possível abrir esta imagem.")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("shows a text instead of an image whose link was refused", async () => {
    respond("POST", LINK, { status: 401, body: { error: "unauthorized", message: "bad key" } });
    renderFile(fileNode("Fachada.png", "image/png"));

    expect(
      await screen.findByText("A API recusou a chave. Confira VITE_API_KEY em web/.env.local."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("shows any other file's type, size and versions", async () => {
    renderFile(fileNode("Tabela.xlsx", "application/vnd.ms-excel"));

    const details = (await screen.findByText("application/vnd.ms-excel")).closest("dl") as HTMLElement;
    expect(within(details).getByText("2,3 MB")).toBeInTheDocument();
    expect(within(details).getByText("2 versões")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(openPdf).not.toHaveBeenCalled();
  });

  it("Baixar asks for a signed link and opens it under the file's name", async () => {
    fakePdf(3);
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    renderFile(fileNode("Condições Gerais 2026.pdf", "application/pdf", 3));

    await userEvent.click(await screen.findByRole("button", { name: "Baixar" }));

    await waitFor(() => expect(click).toHaveBeenCalledTimes(1));
    const link = click.mock.contexts[0] as HTMLAnchorElement;
    expect(link.download).toBe("Condições Gerais 2026.pdf");
    expect(link.getAttribute("href")).toBe(SIGNED);
    expect(calls.find((call) => call.method === "POST" && call.path === LINK)?.key).toBe("test-key");
    expect(calls.some((call) => call.path === RAW)).toBe(false);
  });

  it("Baixar shows the unauthorized text when the key is refused", async () => {
    fakePdf(3);
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    respond("POST", LINK, { status: 401, body: { error: "unauthorized", message: "bad key" } });
    renderFile(fileNode("Condições Gerais 2026.pdf", "application/pdf", 3));

    await userEvent.click(await screen.findByRole("button", { name: "Baixar" }));

    expect(
      await screen.findByText("A API recusou a chave. Confira VITE_API_KEY em web/.env.local."),
    ).toBeInTheDocument();
    expect(click).not.toHaveBeenCalled();
  });

  it("says what the file is, how many versions it has and where it is", async () => {
    fakePdf(3);
    respond("GET", "/v1/nodes/folder-1", {
      body: { ...fileNode("x", "x"), id: "folder-1", parent_id: null, kind: "folder", title: "Residencial", file: null, versions: 0 },
    });
    respond("GET", `/v1/files/${NODE_ID}/versions`, {
      body: [{ id: "v1", size: 1000, replaced_at: "2026-10-20T10:00:00Z" }],
    });
    renderFile(fileNode("Condições Gerais 2026.pdf", "application/pdf", 3));

    expect(await screen.findByText("2 versões · substituído em 20 de out.")).toBeInTheDocument();
    expect(within(screen.getByText(/^Dentro de/)).getByRole("link", { name: "Residencial" })).toHaveAttribute("href", "/kbs/kb-1/n/folder-1");
  });

  it("keeps Substituir and Versões in the ⋯ menu", async () => {
    fakePdf(3);
    respond("GET", `/v1/files/${NODE_ID}/versions`, { body: [] });
    renderFile(fileNode("Condições Gerais 2026.pdf", "application/pdf", 3));

    await userEvent.click(await screen.findByRole("button", { name: "Mais opções do arquivo" }));
    expect(screen.getByRole("menuitem", { name: "Substituir" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("menuitem", { name: "Versões" }));

    const dialog = await screen.findByRole("dialog", { name: "Versões anteriores" });
    expect(await within(dialog).findByText("Nenhuma versão anterior.")).toBeInTheDocument();
  });
});
