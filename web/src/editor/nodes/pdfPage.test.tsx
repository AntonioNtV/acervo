import "@testing-library/jest-dom/vitest";
import { Editor } from "@tiptap/core";
import { MarkdownManager } from "@tiptap/markdown";
import { EditorContent, useEditor } from "@tiptap/react";
import { fireEvent, screen } from "@testing-library/react";
import { useLocation } from "react-router-dom";
import { node, renderInBase, resetApi, respond } from "../../api/testing";
import { blockExtensions } from "../extensions";
import { PageContext } from "./generated";
import { PdfPage, PdfPageWithView } from "./pdfPage";
import { SyncedSource, type SyncedTarget } from "./synced";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

const opened = vi.hoisted(() => ({ pages: 20, password: false, fails: false }));
vi.mock("../../viewer/pdfjs", () => ({
  openPdf: (_source: unknown, onPassword: (submit: () => void, incorrect: boolean) => void) => {
    if (opened.password) onPassword(() => {}, false);
    const render = () => ({ promise: Promise.resolve(), cancel: () => {} });
    const getViewport = ({ scale }: { scale: number }) => ({ width: 612 * scale, height: 792 * scale });
    const doc = { numPages: opened.pages, getPage: () => Promise.resolve({ getViewport, render }) };
    return {
      promise: opened.password || opened.fails ? Promise.reject(new Error("no")) : Promise.resolve(doc),
      destroy: () => {},
    };
  },
}));

// jsdom has no layout, and ProseMirror measures text ranges to scroll the selection into view.
Range.prototype.getClientRects ??= () => [] as unknown as DOMRectList;
Range.prototype.getBoundingClientRect ??= () => new DOMRect();

// Tried before `RawInline`/`RawBlock`, which come later in `blockExtensions`.
const extensions = [PdfPage, ...blockExtensions];
const md = new MarkdownManager({ extensions });

const PDF = "Condições Gerais 2026.pdf";
const toPdf = (title: string): SyncedTarget =>
  title === PDF ? { nodeId: "f-1", href: "/kbs/kb-1/n/f-1" } : "missing";

let shown: Editor | null = null;

function Page({ markdown }: { markdown: string }) {
  shown = useEditor({
    extensions: extensions.map((extension) => (extension.name === "pdfPage" ? PdfPageWithView : extension)),
    content: md.parse(markdown),
  });
  return <EditorContent editor={shown} />;
}

function Where() {
  const location = useLocation();
  return <output>{location.pathname + location.search}</output>;
}

function renderPage(markdown: string) {
  return renderInBase(
    <PageContext.Provider value={{ kbId: "kb-1", nodeId: "p-1" }}>
      <SyncedSource.Provider value={toPdf}>
        <Page markdown={markdown} />
        <Where />
      </SyncedSource.Provider>
    </PageContext.Provider>,
    "/kbs/kb-1/n/p-1",
  );
}

beforeEach(() => {
  resetApi();
  Object.assign(opened, { pages: 20, password: false, fails: false });
});

describe("pdf page block", () => {
  it("reads a line of its own and writes it back in the same form", () => {
    const markdown = `Antes.\n\n[[${PDF}#p=12]]\n\nVer [[${PDF}#p=3]] aqui.`;
    const doc = md.parse(markdown);

    expect(doc.content!.map((block) => block.type)).toEqual(["paragraph", "pdfPage", "paragraph"]);
    expect(doc.content![1]!.attrs).toEqual({ title: PDF, page: 12 });
    expect(md.serialize(doc)).toBe(markdown);

    const created = { type: "pdfPage", attrs: { title: "Tabela.PDF", page: 4 } };
    expect(md.serialize({ type: "doc", content: [created] })).toBe("[[Tabela.PDF#p=4]]");
  });

  it("leaves a synced block and a page link as they were", () => {
    const doc = md.parse("![[Sinistros#Prazos]]\n\n[[Sinistros]]\n\n[[Sinistros#Prazos]]\n\n[[Edital.pdf#p=012]]");

    expect(doc.content!.map((block) => block.type)).toEqual(["syncedBlock", "paragraph", "paragraph", "paragraph"]);
    expect(doc.content!.slice(1).map((block) => block.content?.[0]?.type)).toEqual(["pageLink", "pageLink", "pageLink"]);
  });

  it("draws its page and opens the PDF at it", async () => {
    renderPage(`[[${PDF}#p=12]]\n`);

    expect(await screen.findByRole("img", { name: "Página 12 do PDF" })).toBeInTheDocument();
    expect(screen.getByText("Condições Gerais 2026")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: PDF }));

    expect(screen.getByRole("status")).toHaveTextContent("/kbs/kb-1/n/f-1?p=12");
  });

  it("is picked from the PDFs of the base, with its page", async () => {
    respond("GET", "/v1/kbs/kb-1/search", {
      body: [
        { ...node("p-9", "page", "Condições"), path: "Condições" },
        { ...node("f-1", "file", PDF), path: PDF },
      ],
    });
    renderPage("Antes.\n");
    shown!.commands.setTextSelection(1);
    shown!.commands.insertPdfPage();

    fireEvent.change(await screen.findByRole("textbox", { name: "editor.pdfPage.number" }), { target: { value: "7" } });
    fireEvent.change(screen.getByRole("textbox", { name: "editor.pdfPage.pick" }), { target: { value: "condi" } });
    fireEvent.click(await screen.findByRole("button", { name: PDF }));

    expect(screen.queryByRole("button", { name: "Condições" })).not.toBeInTheDocument();
    expect(shown!.getJSON().content?.find((block) => block.type === "pdfPage")?.attrs).toEqual({
      title: PDF,
      page: 7,
      choosing: false,
    });
  });

  it.each([
    ["a missing or trashed PDF", "Sumiu.pdf", 1, {}, "Nenhuma página com esse nome"],
    ["a page over the last", PDF, 21, {}, /O PDF tem 20 páginas|editor\.pdfPage\.outOfRange/],
    ["a protected PDF", PDF, 1, { password: true }, "Este PDF está protegido por senha."],
    ["a PDF that does not open", PDF, 1, { fails: true }, "Não foi possível abrir este PDF."],
  ])("shows %s with the reason", async (_case, title, page, state, reason) => {
    Object.assign(opened, state);
    renderPage(`[[${title}#p=${page}]]\n`);

    expect(await screen.findByRole("alert")).toHaveTextContent(reason);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
});
