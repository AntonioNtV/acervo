import { Node } from "@tiptap/core";
import type { Node as PmNode } from "@tiptap/pm/model";
import { Plugin, PluginKey, TextSelection } from "@tiptap/pm/state";
import { Decoration, DecorationSet, type EditorView } from "@tiptap/pm/view";
import type { BlockKind } from "../blocks";
import { startBefore } from "../tokenize";
import "./footnote.css";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    footnote: { insertFootnote: () => ReturnType };
  }
}

const REF = /^\[\^([^\]\s]+)\]/;
// One line, plus the indented lines that continue it.
const NOTE = /^ {0,3}\[\^([^\]\s]+)\]:[ \t]?([^\n]*(?:\n(?: {4}|\t)[^\n]*)*)(?:\n|$)/;


const label = (el: HTMLElement) => ({ label: el.dataset.label ?? "" });

/** `[^label]`: a superscript number, by order of first appearance on the page, that leads to its note. */
export const FootnoteRef = Node.create({
  name: "footnoteRef",
  group: "inline",
  inline: true,
  atom: true,
  selectable: true,
  addAttributes: () => ({ label: { default: "" } }),
  parseHTML: () => [{ tag: "sup[data-footnote-ref]", getAttrs: (el) => label(el as HTMLElement) }],
  renderHTML: ({ node }) => [
    "sup",
    { "data-footnote-ref": "", "data-label": node.attrs.label, class: "footnote-ref", role: "doc-noteref" },
  ],
  renderText: ({ node }) => `[^${node.attrs.label}]`,
  markdownTokenizer: {
    name: "footnoteRef",
    level: "inline",
    start: (src) => src.indexOf("[^"),
    tokenize: (src) => {
      const match = REF.exec(src);
      return match ? { type: "footnoteRef", raw: match[0], text: match[1] } : undefined;
    },
  },
  parseMarkdown: (token, h) => h.createNode("footnoteRef", { label: token.text }),
  renderMarkdown: (node) => `[^${node.attrs?.label ?? ""}]`,
});

/** The numbers shown: markers by first appearance, a marker without note in ghost, a note's number before it. */
function numbering(doc: PmNode): DecorationSet {
  const order = new Map<string, number>();
  const refs: Array<{ node: PmNode; pos: number }> = [];
  const notes: Array<{ node: PmNode; pos: number }> = [];
  doc.descendants((node, pos) => {
    if (node.type.name === "footnoteRef") {
      if (!order.has(node.attrs.label)) order.set(node.attrs.label, order.size + 1);
      refs.push({ node, pos });
    } else if (node.type.name === "footnote") notes.push({ node, pos });
  });
  const noted = new Set(notes.map(({ node }) => node.attrs.label as string));
  const decorations = refs.map(({ node, pos }) => {
    const n = String(order.get(node.attrs.label));
    const attrs: Record<string, string> = { "data-n": n, "aria-label": n };
    if (!noted.has(node.attrs.label)) attrs.class = "footnote-ghost";
    return Decoration.node(pos, pos + node.nodeSize, attrs);
  });
  for (const { node, pos } of notes) {
    // A note nobody cites shows its label.
    const shown = String(order.get(node.attrs.label) ?? node.attrs.label);
    const number = () => {
      const span = document.createElement("span");
      span.className = "footnote-number";
      span.contentEditable = "false";
      span.dataset.label = node.attrs.label;
      span.textContent = shown;
      return span;
    };
    decorations.push(Decoration.widget(pos + 1, number, { side: -1, key: `${node.attrs.label}:${shown}` }));
  }
  return DecorationSet.create(doc, decorations);
}

/** A marker scrolls to its note; a note's number back to its first marker. */
function follow(view: EditorView, event: MouseEvent): boolean {
  const target = (event.target as HTMLElement).closest?.("sup[data-footnote-ref], .footnote-number");
  if (!(target instanceof HTMLElement)) return false;
  const wanted = target.matches(".footnote-number") ? "footnoteRef" : "footnote";
  let found = -1;
  view.state.doc.descendants((node, pos) => {
    if (found < 0 && node.type.name === wanted && node.attrs.label === target.dataset.label) found = pos;
    return found < 0;
  });
  if (found < 0) return false;
  (view.nodeDOM(found) as HTMLElement | null)?.scrollIntoView({ block: "center", behavior: "smooth" });
  event.preventDefault();
  return true;
}

/** `[^label]: text`: a note at the end of the page; its label in the file never changes. */
export const Footnote = Node.create({
  name: "footnote",
  group: "block",
  content: "inline*",
  defining: true,
  addAttributes: () => ({ label: { default: "" } }),
  parseHTML: () => [{ tag: "div[data-footnote]", getAttrs: (el) => label(el as HTMLElement) }],
  renderHTML: ({ node }) => [
    "div",
    { "data-footnote": "", "data-label": node.attrs.label, class: "footnote", role: "doc-footnote" },
    0,
  ],
  addCommands() {
    return {
      insertFootnote:
        () =>
        ({ state, tr, dispatch }) => {
          const ref = state.schema.nodes.footnoteRef!;
          let highest = 0;
          state.doc.descendants((node) => {
            const n = Number(node.attrs.label);
            if ((node.type === ref || node.type === this.type) && Number.isInteger(n)) highest = Math.max(highest, n);
          });
          const next = String(highest + 1);
          if (dispatch) {
            tr.replaceSelectionWith(ref.create({ label: next }), false);
            const end = tr.doc.content.size;
            tr.insert(end, this.type.create({ label: next }));
            tr.setSelection(TextSelection.create(tr.doc, end + 1)).scrollIntoView();
          }
          return true;
        },
    };
  },
  addProseMirrorPlugins: () => [
    new Plugin({
      key: new PluginKey("footnoteNumbers"),
      state: {
        init: (_, { doc }) => numbering(doc),
        apply: (tr, numbers) => (tr.docChanged ? numbering(tr.doc) : numbers),
      },
      props: {
        decorations(state) {
          return this.getState(state);
        },
        handleDOMEvents: { click: follow },
      },
    }),
  ],
  markdownTokenizer: {
    name: "footnote",
    level: "block",
    start: startBefore(/^ {0,3}\[\^[^\]\s]+\]:/m),
    tokenize: (src, _tokens, lexer) => {
      const match = NOTE.exec(src);
      if (!match) return undefined;
      const text = (match[2] ?? "").replace(/\n(?: {4}|\t)/g, "\n");
      return { type: "footnote", raw: match[0], label: match[1], tokens: lexer.inlineTokens(text) };
    },
  },
  parseMarkdown: (token, h) => h.createNode("footnote", { label: token.label }, h.parseInline(token.tokens ?? [])),
  renderMarkdown: (node, h) =>
    `[^${node.attrs?.label ?? ""}]: ${h.renderChildren(node.content ?? []).replace(/\n/g, "\n    ")}`,
});

/** After `RawInline` and `RawBlock`, which would keep them as raw text: marked tries the last registered first. */
export const footnoteExtensions = [FootnoteRef, Footnote];

/** Inserted with `insertFootnote()`: the marker at the cursor, its note at the end of the page. */
export const footnoteKinds: BlockKind[] = [{ id: "footnote", group: "blocks" }];
