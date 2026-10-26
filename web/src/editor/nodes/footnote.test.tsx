import { Editor } from "@tiptap/core";
import { blockExtensions, RawBlock } from "../extensions";
import { bindSource, parseMarkdown, serializeMarkdown, type Source } from "../markdown";
import footnotePage from "../fixtures/footnote.md?raw";
import { footnoteExtensions } from "./footnote";

// jsdom has no layout, and ProseMirror measures text ranges to scroll the selection into view.
Range.prototype.getClientRects ??= () => [] as unknown as DOMRectList;
Range.prototype.getBoundingClientRect ??= () => new DOMRect();

const NO_SOURCE: Source = { lead: "", chunks: [], nodes: [] };

function open(markdown: string) {
  const opened = parseMarkdown(markdown);
  const editor = new Editor({ element: document.createElement("div"), extensions: blockExtensions, content: opened.doc });
  return { editor, source: bindSource(opened.source, editor.state.doc) };
}

const types = (editor: Editor) => {
  const found: string[] = [];
  editor.state.doc.descendants((node) => {
    if (node.type.name !== "text") found.push(`${node.type.name}${node.attrs.label ? `:${node.attrs.label}` : ""}`);
  });
  return found;
};

const markers = (editor: Editor) =>
  [...editor.view.dom.querySelectorAll<HTMLElement>("sup[data-footnote-ref]")].map(
    (sup) => `${sup.dataset.label}=${sup.dataset.n}${sup.classList.contains("footnote-ghost") ? " ghost" : ""}`,
  );

describe("footnotes", () => {
  it("are registered after the raw nodes", () => {
    expect(blockExtensions.indexOf(footnoteExtensions[0]!)).toBeGreaterThan(blockExtensions.indexOf(RawBlock));
  });

  it("read the fixture as markers and notes and save it byte for byte", () => {
    const { editor, source } = open(footnotePage);
    expect(types(editor)).toEqual([
      "heading",
      "paragraph",
      "footnoteRef:1",
      "footnoteRef:manual",
      "footnote:1",
      "footnote:manual",
      "paragraph",
      "rawInline",
      "rawBlock",
    ]);
    expect(serializeMarkdown(editor.state.doc, source)).toBe(footnotePage);
    // Rewritten by their own serializers, the notes keep their form, the continuation line included.
    expect(serializeMarkdown(editor.state.doc, NO_SOURCE)).toContain(
      "[^1]: Contados a partir da aprovação.\n\n[^manual]: Manual do corretor, edição 2026.\n    Com uma segunda linha indentada.",
    );
  });

  it("insert the next number at the cursor and its note at the end, where the cursor goes", () => {
    const { editor, source } = open("Prazo[^1] e taxa.\n\n[^1]: Úteis.\n");
    editor.commands.setTextSelection(editor.state.doc.child(0).nodeSize - 2);
    editor.commands.insertFootnote();
    editor.commands.insertContent("Tabela vigente.");
    expect(serializeMarkdown(editor.state.doc, source)).toBe(
      "Prazo[^1] e taxa[^2].\n\n[^1]: Úteis.\n\n[^2]: Tabela vigente.\n",
    );
  });

  it("write an empty note as its label", () => {
    const { editor, source } = open("Prazo[^1].\n\n[^1]: Úteis.\n");
    editor.commands.setTextSelection(editor.state.doc.child(0).nodeSize - 2);
    editor.commands.insertFootnote();
    expect(serializeMarkdown(editor.state.doc, source)).toBe("Prazo[^1][^2].\n\n[^1]: Úteis.\n\n[^2]: \n");
  });

  it("number by first appearance, keeping the labels of the file", () => {
    const { editor, source } = open("A[^b], B[^a] e de novo[^b].\n\n[^a]: Primeira.\n\n[^b]: Segunda.\n\n[^c]: Solta.\n");
    expect(markers(editor)).toEqual(["b=1", "a=2", "b=1"]);
    const numbers = [...editor.view.dom.querySelectorAll(".footnote-number")].map((span) => span.textContent);
    expect(numbers).toEqual(["2", "1", "c"]);
    expect(serializeMarkdown(editor.state.doc, source)).toContain("[^b]");
  });

  it("show a marker without note in ghost", () => {
    const { editor } = open("Com nota[^1] e sem[^2].\n\n[^1]: Existe.\n");
    expect(markers(editor)).toEqual(["1=1", "2=2 ghost"]);
  });
});
