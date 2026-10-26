import { Node, type MarkdownToken } from "@tiptap/core";
import { translate } from "../../i18n";
import type { BlockKind } from "../blocks";
import { startBefore } from "../tokenize";
import "./toggleHeading.css";

type Lexer = { blockTokens: (src: string) => MarkdownToken[] };
type Translate = (key: string, vars?: Record<string, string | number>) => string;

// The summary holds only a heading, on lines of its own; a one-line summary is the plain toggle's.
const OPEN = /^<details( open)?>[ \t]*\n[ \t]*<summary>[ \t]*\n+(#{1,6}[ \t][^\n]*)\n+[ \t]*<\/summary>[ \t]*\n?/;

/** Where the `</details>` closing the one opened before `from` starts, or -1. */
function closingDetails(src: string, from: number): number {
  const tags = /<(\/?)details(?: open)?>/g;
  tags.lastIndex = from;
  let depth = 1;
  for (let match = tags.exec(src); match; match = tags.exec(src)) {
    depth += match[1] ? -1 : 1;
    if (depth === 0) return match.index;
  }
  return -1;
}

/** A heading whose section folds: `<details open><summary>\n\n## Título\n\n</summary>`, `open` saved with the page. */
export const ToggleHeading = Node.create<{ t: Translate }>({
  name: "toggleHeading",
  group: "block",
  content: "heading block*",
  defining: true,
  addOptions: () => ({ t: (key, vars) => translate("ptBR", key, vars) }),
  addAttributes: () => ({
    open: {
      default: true,
      parseHTML: (el) => el.hasAttribute("data-open"),
      renderHTML: (attrs) => (attrs.open ? { "data-open": "" } : {}),
    },
  }),
  parseHTML: () => [{ tag: "div[data-toggle-heading]" }],
  renderHTML: ({ HTMLAttributes }) => ["div", { ...HTMLAttributes, "data-toggle-heading": "" }, 0],
  addNodeView() {
    const { t } = this.options;
    return ({ editor, getPos, node: first }) => {
      const dom = document.createElement("div");
      dom.className = "toggle-heading";
      const caret = document.createElement("button");
      caret.type = "button";
      caret.contentEditable = "false";
      const content = document.createElement("div");
      dom.append(caret, content);

      let node = first;
      const show = () => {
        const open = Boolean(node.attrs.open);
        dom.classList.toggle("is-open", open);
        caret.setAttribute("aria-expanded", String(open));
        caret.setAttribute("aria-label", t(open ? "editor.toggle.close" : "editor.toggle.open"));
        dom.style.setProperty("--toggle-heading-count", JSON.stringify(t("editor.toggleHeading.count", { n: node.childCount - 1 })));
      };
      show();

      caret.addEventListener("click", () => {
        const pos = getPos();
        if (!editor.isEditable || typeof pos !== "number") return;
        editor.view.dispatch(editor.state.tr.setNodeAttribute(pos, "open", !node.attrs.open));
      });

      return {
        dom,
        contentDOM: content,
        ignoreMutation: (mutation) =>
          mutation.type !== "selection" && (mutation.target === dom || caret.contains(mutation.target)),
        update: (updated) => {
          if (updated.type !== node.type) return false;
          node = updated;
          show();
          return true;
        },
      };
    };
  },
  markdownTokenizer: {
    name: "toggleHeading",
    level: "block",
    start: startBefore(/^<details/m),
    tokenize: (src: string, _tokens: MarkdownToken[], lexer: Lexer) => {
      const open = OPEN.exec(src);
      if (!open) return undefined;
      const close = closingDetails(src, open[0].length);
      if (close < 0) return undefined;
      const end = /^<\/details>[ \t]*(?:\n|$)/.exec(src.slice(close));
      if (!end) return undefined;
      const inner = src.slice(open[0].length, close).replace(/^\n+|\n+$/g, "");
      return {
        type: "toggleHeading",
        raw: src.slice(0, close + end[0].length),
        open: Boolean(open[1]),
        heading: lexer.blockTokens(open[2]!),
        tokens: lexer.blockTokens(inner),
      };
    },
  },
  parseMarkdown: (token, h) =>
    h.createNode("toggleHeading", { open: token.open }, [
      ...h.parseChildren(token.heading ?? []),
      ...h.parseChildren(token.tokens ?? []),
    ]),
  renderMarkdown: (node, h) => {
    const [heading, ...blocks] = node.content ?? [];
    const inner = h.renderChildren(blocks, "\n\n");
    const head = `<details${node.attrs?.open ? " open" : ""}>\n<summary>\n\n${heading ? h.renderChildren([heading]) : ""}\n\n</summary>`;
    return inner.trim() ? `${head}\n\n${inner}\n\n</details>` : `${head}\n\n</details>`;
  },
});

export const toggleHeadingKinds: BlockKind[] = [
  {
    id: "toggleHeading",
    group: "blocks",
    turn: (c) => c.clearNodes().setHeading({ level: 2 }).wrapIn("toggleHeading", { open: true }),
  },
];
