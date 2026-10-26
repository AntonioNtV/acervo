import { Editor, getSchema, type JSONContent } from "@tiptap/core";
import { MarkdownManager } from "@tiptap/markdown";
import { blockAt } from "../BlockHandle";
import { blockExtensions } from "../extensions";
import { Columns } from "./columns";

const extensions = [Columns, ...blockExtensions];
const manager = new MarkdownManager({ extensions });
const schema = getSchema(extensions);

const form = (bodies: string[]) =>
  [
    `<!-- acervo:columns ${bodies.length} -->`,
    bodies.map((body, i) => `<!-- acervo:column ${i + 1} -->\n${body}`).join("\n\n"),
    "<!-- acervo:/columns -->",
  ].join("\n");

const paragraph = (text: string): JSONContent => ({ type: "paragraph", content: [{ type: "text", text }] });
const column = (...texts: string[]): JSONContent => ({ type: "column", content: texts.map(paragraph) });
const types = (doc: JSONContent) => (doc.content ?? []).map((node) => node.type);

// Without the empty paragraph the editor keeps at the end of the page.
const blocks = (editor: Editor) => (editor.getJSON().content ?? []).filter((node) => node.type !== "paragraph" || node.content);

function editorWith(...columns: JSONContent[]) {
  return new Editor({ extensions, content: { type: "doc", content: [{ type: "columns", content: columns }] } });
}

/** Where the first paragraph holding `text` starts. */
function paragraphAt(editor: Editor, text: string): number {
  let found = -1;
  editor.state.doc.descendants((node, pos) => {
    if (found < 0 && node.type.name === "paragraph" && node.textContent === text) found = pos;
    return found < 0;
  });
  return found;
}

describe("Columns", () => {
  it.each([
    ["two", ["Prazo de **3 dias**.", "- RG\n- CNH"]],
    ["five", ["Um", "## Dois", "Três\n\nE mais", "> Quatro", "Cinco"]],
  ])("%s columns read as the node and write back byte for byte", (_name, bodies) => {
    const markdown = form(bodies);
    const doc = manager.parse(markdown);
    expect(types(doc)).toEqual(["columns"]);
    expect(types(doc.content![0]!)).toEqual(bodies.map(() => "column"));
    expect(manager.serialize(doc)).toBe(markdown);
  });

  it("writes an edited one in the same form", () => {
    const node = schema.nodeFromJSON({ type: "doc", content: [{ type: "columns", content: [column("A", "B"), column("C")] }] });
    expect(manager.serialize(node.toJSON())).toBe(form(["A\n\nB", "C"]));
  });

  it.each([
    ["no closing", "<!-- acervo:columns 2 -->\n<!-- acervo:column 1 -->\nUm\n\n<!-- acervo:column 2 -->\nDois\n"],
    ["count not matching", form(["Um", "Dois"]).replace("columns 2", "columns 3")],
    ["columns out of order", form(["Um", "Dois"]).replace("column 2", "column 3")],
    ["one column", form(["Um"])],
  ])("%s stays raw, unchanged", (_name, markdown) => {
    const tokens = manager.instance.lexer(markdown);
    // What the page's parser needs to keep each block as written.
    expect(tokens.map((token) => token.raw).join("")).toBe(markdown);
    expect(tokens.some((token) => token.type === "columns")).toBe(false);
  });

  it("emptying a column of two leaves plain blocks", () => {
    const editor = editorWith(column("Um", "Dois"), column("Três"));
    const pos = paragraphAt(editor, "Três");
    editor.commands.deleteRange({ from: pos, to: pos + editor.state.doc.nodeAt(pos)!.nodeSize });
    expect(blocks(editor)).toEqual([paragraph("Um"), paragraph("Dois")]);
  });

  it("emptying one of three columns removes only that column", () => {
    const editor = editorWith(column("Um"), column("Dois"), column("Três"));
    // As the handle's drag takes it out: the block selected whole, then deleted.
    editor.chain().setNodeSelection(paragraphAt(editor, "Dois")).deleteSelection().run();
    expect(blocks(editor)).toEqual([{ type: "columns", content: [column("Um"), column("Três")] }]);
  });

  it("a row moved into a column becomes its blocks", () => {
    const editor = editorWith(column("Um"), column("Dois"));
    const row = { type: "columns", content: [column("A"), column("B")] };
    editor.commands.insertContentAt(paragraphAt(editor, "Dois"), row);
    expect(blocks(editor)).toEqual([
      { type: "columns", content: [column("Um"), column("A", "B", "Dois")] },
    ]);
  });

  it('"columns" puts the current block in the first of two', () => {
    const editor = new Editor({ extensions, content: { type: "doc", content: [paragraph("Antes"), paragraph("Prazo")] } });
    editor.commands.setTextSelection(paragraphAt(editor, "Prazo") + 2);
    editor.commands.setColumns();
    expect(blocks(editor)).toEqual([
      paragraph("Antes"),
      { type: "columns", content: [column("Prazo"), { type: "column", content: [{ type: "paragraph" }] }] },
    ]);
    expect(editor.can().setColumns()).toBe(false);
  });

  it("the handle finds a block inside a column", () => {
    const editor = editorWith(column("Um"), column("Dois"));
    const wrapper = document.createElement("div");
    const text = editor.view.dom.querySelectorAll("[data-column] p")[1]!;
    expect(blockAt(editor, wrapper, text)?.pos).toBe(paragraphAt(editor, "Dois"));
    expect(blockAt(editor, wrapper, editor.view.dom.querySelector("[data-columns]"))?.pos).toBe(0);
  });
});
