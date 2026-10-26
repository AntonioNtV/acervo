import { Extension, Node, type MarkdownToken } from "@tiptap/core";
import type { Node as PmNode } from "@tiptap/pm/model";
import { Plugin, TextSelection } from "@tiptap/pm/state";
import type { BlockKind } from "../blocks";
import "./columns.css";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    columns: { setColumns: () => ReturnType };
  }
}

type Lexer = { blockTokens: (src: string) => MarkdownToken[] };

const OPEN = /^<!-- acervo:columns (\d+) -->[ \t]*\n/;
const CLOSE = /^<!-- acervo:\/columns -->[ \t]*(?:\n|$)/m;
const MARKER = /^<!-- acervo:column (\d+) -->[ \t]*(?:\n|$)/gm;

/** The bodies of `inner`, one per `<!-- acervo:column i -->`; null unless they are exactly 1…count, from the top. */
function columnBodies(inner: string, count: number): string[] | null {
  const markers = [...inner.matchAll(MARKER)];
  if (markers.length !== count || markers[0]?.index !== 0) return null;
  if (markers.some((marker, i) => Number(marker[1]) !== i + 1)) return null;
  return markers.map((marker, i) =>
    inner.slice(marker.index + marker[0].length, markers[i + 1]?.index ?? inner.length).replace(/^\n+|\n+$/g, ""),
  );
}

// Same as `startBefore` in extensions.ts: searching the whole rest of the page on each paragraph is quadratic.
const start = (src: string) => {
  const blank = src.indexOf("\n\n");
  if (blank < 0) return src.search(/^<!-- acervo:columns /m);
  const found = src.slice(0, blank).search(/^<!-- acervo:columns /m);
  return found < 0 ? blank + 1 : found;
};

/** One column: any blocks but columns. Isolating, so turning or deleting a block never splits the row. */
export const Column = Node.create({
  name: "column",
  // Empty only for a moment: the normalizer then drops it.
  content: "block*",
  isolating: true,
  parseHTML: () => [{ tag: "div[data-column]" }],
  renderHTML: () => ["div", { "data-column": "" }, 0],
});

const blocksOf = (columns: readonly PmNode[]) => columns.flatMap((column) => column.children);

/**
 * After each edit: an emptied column goes away, a row left with one column becomes its blocks, and a row that ended
 * up inside a column (dropped or pasted there) becomes its blocks too.
 */
const ColumnsNormalizer = Extension.create({
  name: "columnsNormalizer",
  addProseMirrorPlugins: () => [
    new Plugin({
      appendTransaction: (transactions, _old, state) => {
        if (!transactions.some((tr) => tr.docChanged)) return null;
        const found: number[] = [];
        state.doc.descendants((node, pos) => {
          if (node.type.name === "columns") found.push(pos);
          return !node.isTextblock;
        });
        const tr = state.tr;
        for (const at of found.reverse()) {
          const pos = tr.mapping.map(at);
          const row = tr.doc.nodeAt(pos);
          if (!row) continue;
          const $pos = tr.doc.resolve(pos);
          const nested = Array.from({ length: $pos.depth }, (_, d) => $pos.node(d + 1)).some(
            (node) => node.type.name === "column",
          );
          const kept = row.children.filter((column) => column.childCount > 0);
          if (nested || kept.length < 2) tr.replaceWith(pos, pos + row.nodeSize, blocksOf(kept));
          else if (kept.length < row.childCount) tr.replaceWith(pos, pos + row.nodeSize, row.type.create(row.attrs, kept));
        }
        return tr.docChanged ? tr : null;
      },
    }),
  ],
});

/** 2–5 columns side by side, between `<!-- acervo:columns N -->` and `<!-- acervo:/columns -->`. */
export const Columns = Node.create({
  name: "columns",
  group: "block",
  content: "column{2,5}",
  defining: true,
  parseHTML: () => [{ tag: "div[data-columns]" }],
  renderHTML: () => ["div", { "data-columns": "", class: "columns" }, 0],
  addCommands() {
    return {
      setColumns:
        () =>
        ({ tr, state, dispatch }) => {
          const { $from, $to } = tr.selection;
          for (let depth = $from.depth; depth > 0; depth--) if ($from.node(depth).type.name === "column") return false;
          const from = $from.posAtIndex($from.index(0), 0);
          const to = $to.posAtIndex(Math.max($to.indexAfter(0), $from.index(0) + 1), 0);
          const { column, paragraph } = state.schema.nodes;
          if (!column || !paragraph) return false;
          if (dispatch) {
            const row = this.type.create(null, [
              column.create(null, tr.doc.content.cut(from, to)),
              column.create(null, paragraph.create()),
            ]);
            tr.replaceWith(from, to, row).setSelection(TextSelection.near(tr.doc.resolve(from + 2)));
          }
          return true;
        },
    };
  },
  addExtensions: () => [Column, ColumnsNormalizer],
  markdownTokenizer: {
    name: "columns",
    level: "block",
    start,
    tokenize: (src: string, _tokens: MarkdownToken[], lexer: Lexer) => {
      const open = OPEN.exec(src);
      if (!open) return undefined;
      const count = Number(open[1]);
      if (count < 2 || count > 5) return undefined;
      const rest = src.slice(open[0].length);
      const close = CLOSE.exec(rest);
      if (!close) return undefined;
      const inner = rest.slice(0, close.index);
      if (/^<!-- acervo:columns /m.test(inner)) return undefined;
      const bodies = columnBodies(inner, count);
      if (!bodies) return undefined;
      return {
        type: "columns",
        raw: src.slice(0, open[0].length + close.index + close[0].length),
        columns: bodies.map((body) => lexer.blockTokens(body)),
      };
    },
  },
  parseMarkdown: (token, h) =>
    h.createNode(
      "columns",
      undefined,
      (token.columns as MarkdownToken[][]).map((tokens) => {
        const content = h.parseChildren(tokens);
        return h.createNode("column", undefined, content.length ? content : [{ type: "paragraph" }]);
      }),
    ),
  renderMarkdown: (node, h) => {
    const columns = node.content ?? [];
    const body = columns
      .map((column, i) => {
        const inner = h.renderChildren(column.content ?? [], "\n\n");
        return `<!-- acervo:column ${i + 1} -->${inner ? `\n${inner}` : ""}`;
      })
      .join("\n\n");
    return `<!-- acervo:columns ${columns.length} -->\n${body}\n<!-- acervo:/columns -->`;
  },
});

export const columnsKinds: BlockKind[] = [{ id: "columns", group: "blocks", turn: (c) => c.setColumns() }];
