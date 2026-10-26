import "@testing-library/jest-dom/vitest";
import { act, screen, waitFor, within } from "@testing-library/react";
import { getSchema } from "@tiptap/core";
import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import { MemoryRouter } from "react-router-dom";
import { node, renderWithApi, resetApi, respond } from "../../api/testing";
import { fakeBases, summary } from "../../screens/bases/testing";
import { blockExtensions } from "../extensions";
import { bindSource, parseMarkdown, serializeMarkdown, type Source } from "../markdown";
import { generatedExtensions, PageContext } from "./generated";

// markdown.ts builds its one manager from `blockExtensions`: here they are the page's with the generated blocks last,
// since marked tries the tokenizer registered last first.
vi.mock("../extensions", async (importOriginal) => {
  const original = await importOriginal<typeof import("../extensions")>();
  const { generatedExtensions: generated } = await import("./generated");
  return { ...original, blockExtensions: [...original.blockExtensions, ...generated] };
});
vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

const NO_SOURCE: Source = { lead: "", chunks: [], nodes: [] };
const PAGE = "# Renovação\n\n<!-- toc -->\n\nTexto.\n\n<!-- acervo:breadcrumb -->\n\n<!-- origem: CG.pdf p. 3 -->\n\n<!--  toc -->\n";

function Page({ markdown, onEditor }: { markdown: string; onEditor?: (editor: Editor) => void }) {
  const editor = useEditor({
    extensions: blockExtensions,
    content: parseMarkdown(markdown).doc,
    onCreate: ({ editor: created }) => onEditor?.(created as Editor),
  });
  return <EditorContent editor={editor} />;
}

function renderPage(markdown: string, onEditor?: (editor: Editor) => void) {
  return renderWithApi(
    <MemoryRouter>
      <PageContext.Provider value={{ kbId: "kb-1", nodeId: "renovacao" }}>
        <Page markdown={markdown} onEditor={onEditor} />
      </PageContext.Provider>
    </MemoryRouter>,
  );
}

const links = () =>
  within(screen.getByRole("navigation", { name: "editor.block.toc" }))
    .queryAllByRole("button")
    .map((button) => `${button.classList.contains("toc-h3") ? "  " : ""}${button.textContent}`);

beforeEach(() => {
  resetApi();
  fakeBases([summary({ id: "kb-1", name: "Seguros" })]);
  respond("GET", "/v1/nodes/renovacao", { body: node("renovacao", "page", "Renovação", "bradesco") });
  respond("GET", "/v1/nodes/bradesco", { body: node("bradesco", "folder", "Bradesco") });
});

describe("generated blocks", () => {
  it("are registered after the raw nodes", () => {
    expect(blockExtensions.slice(-2)).toEqual(generatedExtensions);
  });

  it("read the comments alone on their line as blocks, keep other comments raw, and save byte for byte", () => {
    const { doc, source } = parseMarkdown(PAGE);
    expect(doc.content?.map((block) => block.type)).toEqual([
      "heading",
      "tableOfContents",
      "paragraph",
      "breadcrumb",
      "rawBlock",
      "rawBlock",
    ]);
    const page = getSchema(blockExtensions).nodeFromJSON(doc);
    expect(serializeMarkdown(page, bindSource(source, page))).toBe(PAGE);
    expect(serializeMarkdown(page, NO_SOURCE)).toBe(PAGE);
  });

  it("list the ## and ### headings, ### indented, and follow the page as it changes", async () => {
    let editor: Editor | undefined;
    renderPage("# Título\n\n<!-- toc -->\n\n## Prazos\n\n### Úteis\n\n#### Fundo\n", (created) => (editor = created));
    await waitFor(() => expect(links()).toEqual(["Prazos", "  Úteis"]));

    act(() => {
      editor!.commands.insertContentAt(editor!.state.doc.content.size, "<h2>Documentos</h2>");
    });
    expect(links()).toEqual(["Prazos", "  Úteis", "Documentos"]);
  });

  it("show one ghost line on a page without headings", async () => {
    renderPage("<!-- toc -->\n\nSó texto.\n");
    expect(await screen.findByText("editor.toc.empty")).toHaveClass("toc-empty");
  });

  it("show the path to the page from the page it is on", async () => {
    renderPage("<!-- acervo:breadcrumb -->\n");
    const trail = await screen.findByRole("navigation", { name: "Caminho" });
    expect(await within(trail).findByRole("link", { name: "Bradesco" })).toHaveAttribute("href", "/kbs/kb-1/n/bradesco");
    expect(within(trail).getByText("Renovação")).toBeInTheDocument();
  });
});
