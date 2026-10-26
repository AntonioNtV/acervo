import "@testing-library/jest-dom/vitest";
import { Editor } from "@tiptap/core";
import { EditorContent, useEditor } from "@tiptap/react";
import { act, fireEvent, screen } from "@testing-library/react";
import { MarkdownManager } from "@tiptap/markdown";
import { renderInBase, resetApi, respond } from "../../api/testing";
import { blockExtensions } from "../extensions";
import { SyncedBlock, SyncedBlockWithView, SyncedSource, type SyncedTarget } from "./synced";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

// jsdom has no layout, and ProseMirror measures text ranges to scroll the selection into view.
Range.prototype.getClientRects ??= () => [] as unknown as DOMRectList;
Range.prototype.getBoundingClientRect ??= () => new DOMRect();

// Last, after `RawInline` and `RawBlock`: marked tries the tokenizer registered last first. The view's own text is read
// by markdown.ts, whose manager here has no synced block.
const extensions = [...blockExtensions, SyncedBlock];
const md = new MarkdownManager({ extensions });

const RENEWAL = [
  "# Renovação",
  "",
  "Aviso 30 dias antes.",
  "",
  "## Documentos",
  "",
  "Boleto da 1ª parcela no portal.",
  "",
  "```",
  "## não é seção",
  "```",
  "",
  "## Prazos",
  "",
  "Cinco dias úteis.",
].join("\n");

const page = (markdown: string) => ({
  markdown,
  links: {},
  revision: 1,
  saved_at: "2026-10-25T10:00:00Z",
  version_id: "v-1",
  sections: [
    { anchor: "documentos", heading: "Documentos" },
    { anchor: "prazos", heading: "Prazos" },
  ],
});

const toRenewal = (title: string): SyncedTarget =>
  title === "Renovação" ? { nodeId: "p-2", href: "/kbs/kb-1/n/p-2" } : "missing";

let shown: Editor | null = null;

function Page({ markdown }: { markdown: string }) {
  shown = useEditor({
    extensions: [...blockExtensions, SyncedBlockWithView],
    content: md.parse(markdown),
  });
  return <EditorContent editor={shown} />;
}

function renderPage(markdown: string, source: (title: string) => SyncedTarget = toRenewal, path = "/kbs/kb-1/n/p-1") {
  return renderInBase(
    <SyncedSource.Provider value={source}>
      <Page markdown={markdown} />
    </SyncedSource.Provider>,
    path,
  );
}

beforeEach(() => {
  resetApi();
  respond("GET", "/v1/pages/p-2", { body: page(RENEWAL) });
});

describe("synced block", () => {
  it("reads a line of its own and writes it back in the same form", () => {
    const markdown = "Antes.\n\n![[Renovação#Documentos]]\n\n![[Renovação]]\n\nVer ![[Renovação]] aqui.";
    const doc = md.parse(markdown);

    expect(doc.content!.map((node) => node.type)).toEqual(["paragraph", "syncedBlock", "syncedBlock", "paragraph"]);
    expect(doc.content![1]!.attrs).toEqual({ title: "Renovação", section: "Documentos" });
    expect(doc.content![2]!.attrs).toEqual({ title: "Renovação", section: null });
    expect(md.serialize(doc)).toBe(markdown);

    const created = { type: "syncedBlock", attrs: { title: "Sinistro", section: "Prazos" } };
    expect(md.serialize({ type: "doc", content: [created] })).toBe("![[Sinistro#Prazos]]");
  });

  it("is made by a page picked after the `!`, then asks the section", () => {
    const editor = new Editor({ element: document.createElement("div"), extensions });
    editor.commands.insertSyncedBlock();
    expect(editor.getText()).toBe("![[");

    editor.commands.setContent({ type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text: "!" }] }] });
    editor.commands.setTextSelection(2);
    editor.commands.insertContent([{ type: "pageLink", attrs: { title: "Renovação" } }, { type: "text", text: " " }]);

    expect(editor.getJSON().content?.[0]).toEqual({
      type: "syncedBlock",
      attrs: { title: "Renovação", section: null, choosing: true },
    });
  });

  it("shows only its section, from its heading to the next", async () => {
    renderPage("![[Renovação#Documentos]]\n");

    expect(await screen.findByText("Boleto da 1ª parcela no portal.")).toBeInTheDocument();
    expect(screen.getByText("## não é seção")).toBeInTheDocument();
    expect(screen.queryByText("Cinco dias úteis.")).not.toBeInTheDocument();
    expect(screen.queryByText("Aviso 30 dias antes.")).not.toBeInTheDocument();
  });

  it("lists the sections once inserted and keeps the one picked", async () => {
    renderPage("Antes.\n");
    act(() => {
      shown!.commands.insertContentAt(0, { type: "syncedBlock", attrs: { title: "Renovação", choosing: true } });
    });

    fireEvent.click(await screen.findByRole("button", { name: "Prazos" }));

    expect(await screen.findByText("Cinco dias úteis.")).toBeInTheDocument();
    expect(shown!.getJSON().content?.[0]?.attrs).toEqual({ title: "Renovação", section: "Prazos", choosing: false });
  });

  it.each([
    ["a missing page", "![[Sinistro]]\n", "/kbs/kb-1/n/p-1"],
    ["a missing section", "![[Renovação#Vistoria]]\n", "/kbs/kb-1/n/p-1"],
    ["the page itself", "![[Renovação]]\n", "/kbs/kb-1/n/p-2"],
  ])("shows %s as gone and unlinks by deleting the block", async (_case, markdown, path) => {
    renderPage(markdown, toRenewal, path);

    expect(await screen.findByRole("alert")).toHaveTextContent("A seção de origem foi apagada.");
    fireEvent.click(screen.getByRole("button", { name: "Desvincular" }));

    expect(shown!.getJSON().content?.some((node) => node.type === "syncedBlock")).toBe(false);
  });
});
