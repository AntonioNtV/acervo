import { InputRule, Node, type AnyExtension, type JSONContent, type MarkdownToken } from "@tiptap/core";
import { Details, DetailsContent, DetailsSummary } from "@tiptap/extension-details";
import { TaskItem, TaskList } from "@tiptap/extension-list";
import { Paragraph } from "@tiptap/extension-paragraph";
import { Table, TableKit } from "@tiptap/extension-table";
import StarterKit from "@tiptap/starter-kit";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    callout: { setCallout: () => ReturnType };
  }
}

const textOf = (node: JSONContent): string => node.text ?? (node.content ?? []).map(textOf).join("");

// The server's rule (pages/links.py): no brackets inside the target.
const PAGE_LINK = /^\[\[([^[\]]+)\]\]/;

/** `[[Título]]`: a link to another page of the base, resolved by title when shown. */
export const PageLink = Node.create({
  name: "pageLink",
  group: "inline",
  inline: true,
  atom: true,
  selectable: true,
  addAttributes: () => ({ title: { default: "" } }),
  parseHTML: () => [
    { tag: "span[data-page-link]", getAttrs: (el) => ({ title: (el as HTMLElement).dataset.pageLink ?? "" }) },
  ],
  renderHTML: ({ node }) => ["span", { "data-page-link": node.attrs.title }, `[[${node.attrs.title}]]`],
  renderText: ({ node }) => `[[${node.attrs.title}]]`,
  markdownTokenizer: {
    name: "pageLink",
    level: "inline",
    start: (src) => src.indexOf("[["),
    tokenize: (src) => {
      const match = PAGE_LINK.exec(src);
      return match ? { type: "pageLink", raw: match[0], text: match[1] } : undefined;
    },
  },
  parseMarkdown: (token, h) => h.createNode("pageLink", { title: token.text }),
  renderMarkdown: (node) => `[[${node.attrs?.title ?? ""}]]`,
  addInputRules() {
    return [
      new InputRule({
        find: /\[\[([^[\]]+)\]\]$/,
        handler: ({ state, range, match }) => {
          state.tr.replaceWith(range.from, range.to, this.type.create({ title: match[1] }));
        },
      }),
    ];
  },
});

// Inline HTML (a provenance comment, `<br>`, `<sup>`), images, footnote and reference links are kept exactly as
// written: each block is read on its own, without the page's definitions, and the schema has no image.
const RAW_INLINE =
  /^(?:<!--[\s\S]*?-->|!\[[^\]\n]*\]\([^)\n]*\)|<\/?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?\/?>|\[\^[^\]\s]+\]|\[[^[\]\n]+\]\[[^[\]\n]*\])/;

export const RawInline = Node.create({
  name: "rawInline",
  group: "inline",
  inline: true,
  atom: true,
  addAttributes: () => ({ markdown: { default: "" } }),
  parseHTML: () => [{ tag: "span[data-raw]", getAttrs: (el) => ({ markdown: (el as HTMLElement).dataset.raw ?? "" }) }],
  renderHTML: ({ node }) => ["span", { "data-raw": node.attrs.markdown, class: "raw-inline" }, node.attrs.markdown],
  renderText: ({ node }) => node.attrs.markdown,
  markdownTokenizer: {
    name: "rawInline",
    level: "inline",
    start: (src) => src.search(/<|!?\[/),
    tokenize: (src) => {
      const match = RAW_INLINE.exec(src);
      return match ? { type: "rawInline", raw: match[0], text: match[0] } : undefined;
    },
  },
  parseMarkdown: (token, h) => h.createNode("rawInline", { markdown: token.raw }),
  renderMarkdown: (node) => node.attrs?.markdown ?? "",
});

/**
 * A block tokenizer's `start`: where `pattern` (one line) first matches before the next blank line, else that blank
 * line. marked asks it before each paragraph to stop the paragraph there, and no paragraph runs past a blank line;
 * searching the whole rest of the page each time made opening a long page quadratic. Answering the blank line, not
 * -1, keeps the paragraph marked as cut, which is how a line the tokenizers then reject is joined back to it.
 */
const startBefore = (pattern: RegExp) => (src: string) => {
  const blank = src.indexOf("\n\n");
  if (blank < 0) return src.search(pattern);
  const found = src.slice(0, blank).search(pattern);
  return found < 0 ? blank + 1 : found;
};

// Link reference and footnote definitions: marked would otherwise take them out of the token stream.
const DEFINITION = /^ {0,3}\[[^\]\n]+\]:[^\n]*(?:\n(?: {4}|\t)[^\n]*)*(?:\n|$)/;

/** Markdown the editor has no block for (HTML, footnotes, definitions): its text, saved back untouched. */
export const RawBlock = Node.create({
  name: "rawBlock",
  group: "block",
  content: "text*",
  marks: "",
  code: true,
  defining: true,
  parseHTML: () => [{ tag: "pre[data-raw-block]", preserveWhitespace: "full" }],
  renderHTML: () => ["pre", { "data-raw-block": "", class: "raw-block" }, 0],
  markdownTokenName: "html",
  markdownTokenizer: {
    name: "rawDefinition",
    level: "block",
    // Without `start`, @tiptap/markdown probes with a new lexer, which takes marked's shared tokenizer from the one
    // running and leaves every paragraph without its inline tokens.
    start: startBefore(/^ {0,3}\[[^\]\n]+\]:/m),
    tokenize: (src) => {
      const match = DEFINITION.exec(src);
      return match ? { type: "html", raw: match[0], text: match[0], block: true } : undefined;
    },
  },
  parseMarkdown: (token, h) => {
    const raw = (token.raw ?? "").replace(/\n+$/, "");
    return h.createNode("rawBlock", undefined, raw ? [h.createTextNode(raw)] : []);
  },
  renderMarkdown: (node) => textOf(node),
});

export const CALLOUT_KINDS = ["NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION"] as const;
const CALLOUT = new RegExp(
  `^ {0,3}> ?\\[!(${CALLOUT_KINDS.join("|")})\\][ \\t]*(?:\\n|$)((?: {0,3}>[^\\n]*(?:\\n|$))*)`,
);

/** A GFM alert, `> [!NOTE]`: renders on GitHub and survives an export. */
export const Callout = Node.create({
  name: "callout",
  group: "block",
  content: "block+",
  defining: true,
  addAttributes: () => ({ kind: { default: "NOTE" } }),
  parseHTML: () => [{ tag: "div[data-callout]", getAttrs: (el) => ({ kind: (el as HTMLElement).dataset.callout }) }],
  renderHTML: ({ node }) => ["div", { "data-callout": node.attrs.kind, class: "callout" }, 0],
  addCommands() {
    return {
      setCallout:
        () =>
        ({ commands }) =>
          commands.wrapIn(this.name),
    };
  },
  markdownTokenizer: {
    name: "callout",
    level: "block",
    start: startBefore(/^ {0,3}> ?\[!/m),
    tokenize: (src, _tokens, lexer) => {
      const match = CALLOUT.exec(src);
      if (!match) return undefined;
      const inner = (match[2] ?? "").replace(/^ {0,3}> ?/gm, "");
      return { type: "callout", raw: match[0], kind: match[1], tokens: lexer.blockTokens(inner) };
    },
  },
  parseMarkdown: (token, h) => {
    const content = h.parseChildren(token.tokens ?? []);
    return h.createNode("callout", { kind: token.kind }, content.length ? content : [{ type: "paragraph" }]);
  },
  renderMarkdown: (node, h) => {
    const inner = h.renderChildren(node.content ?? [], "\n\n");
    const lines = inner ? inner.split("\n").map((line) => (line.trim() ? `> ${line}` : ">")) : [];
    return [`> [!${node.attrs?.kind ?? "NOTE"}]`, ...lines].join("\n");
  },
});

/** Where the `</details>` closing the one opened before `from` starts, or -1. */
function closingDetails(src: string, from: number): number {
  const tags = /<(\/?)details>/g;
  tags.lastIndex = from;
  let depth = 1;
  for (let match = tags.exec(src); match; match = tags.exec(src)) {
    depth += match[1] ? -1 : 1;
    if (depth === 0) return match.index;
  }
  return -1;
}

const DETAILS_OPEN = /^<details>[ \t]*\n?[ \t]*<summary>([^\n]*?)<\/summary>[ \t]*\n?/;

type Lexer = { blockTokens: (src: string) => MarkdownToken[] };

/** A toggle is `<details><summary>`: it renders on GitHub, and Markdown inside it stays Markdown. */
export const Toggle = Details.extend({
  markdownTokenName: "details",
  markdownTokenizer: {
    name: "details",
    level: "block",
    start: startBefore(/^<details>/m),
    tokenize: (src: string, _tokens: MarkdownToken[], lexer: Lexer) => {
      const open = DETAILS_OPEN.exec(src);
      if (!open) return undefined;
      const close = closingDetails(src, open[0].length);
      if (close < 0) return undefined;
      const end = /^<\/details>[ \t]*(?:\n|$)/.exec(src.slice(close));
      if (!end) return undefined;
      const inner = src.slice(open[0].length, close).replace(/^\n+|\n+$/g, "");
      return {
        type: "details",
        raw: src.slice(0, close + end[0].length),
        summary: open[1],
        tokens: lexer.blockTokens(inner),
      };
    },
  },
  parseMarkdown: (token, h) => {
    const content = h.parseChildren(token.tokens ?? []);
    return h.createNode("details", undefined, [
      h.createNode("detailsSummary", undefined, token.summary ? [h.createTextNode(token.summary)] : []),
      h.createNode("detailsContent", undefined, content.length ? content : [{ type: "paragraph" }]),
    ]);
  },
  renderMarkdown: (node, h) => {
    const [summary, content] = node.content ?? [];
    const inner = content ? h.renderChildren(content.content ?? [], "\n\n") : "";
    const head = `<details>\n<summary>${summary ? textOf(summary) : ""}</summary>`;
    return inner.trim() ? `${head}\n\n${inner}\n\n</details>` : `${head}\n\n</details>`;
  },
});

const LIST_MARKER = /^( {0,3})([-+*]|\d{1,9}[.)])(?=[ \t]|$)/gm;

/** A line of text that starts like a list item is escaped (`1\.`, `\-`), so it reads back as the same paragraph. */
const TextParagraph = Paragraph.extend({
  renderMarkdown(node, h, context) {
    const markdown = this.parent?.(node, h, context) ?? "";
    return markdown.replace(LIST_MARKER, (_line, indent: string, marker: string) =>
      /\d/.test(marker) ? `${indent}${marker.slice(0, -1)}\\${marker.slice(-1)}` : `${indent}\\${marker}`,
    );
  },
});

// Their own `:::` syntax would turn such text in a page into blocks; the toggle writes them instead.
const noMarkdown = { markdownTokenizer: null, parseMarkdown: null, renderMarkdown: null } as unknown as object;

/** `[] ` or `[ ] ` at the start of a line or of a bulleted item makes a to-do (a bulleted list turns whole). */
const TodoItem = TaskItem.extend({
  addInputRules() {
    return [
      new InputRule({
        find: /^\[( |x)?\]\s$/,
        handler: ({ state, range, match, chain }) => {
          const $from = state.doc.resolve(range.from);
          const item = $from.node(-1)?.type.name;
          const bulleted = item === "listItem" && $from.node(-2)?.type.name === "bulletList";
          if ((item === "listItem" || item === "taskItem") && !bulleted) return null;
          chain()
            .deleteRange(range)
            .toggleList("taskList", "taskItem")
            .updateAttributes("taskItem", { checked: match[1] === "x" })
            .run();
        },
      }),
      ...(this.parent?.() ?? []),
    ];
  },
});

// TaskList's tokenizer and Table's `start` split the whole rest of the page on every call, which made opening a long
// page quadratic. Each now gets the source only as far as it reads.
const taskListTokenizer = TaskList.config.markdownTokenizer!;
const BoundedTaskList = TaskList.extend({
  markdownTokenizer: {
    ...taskListTokenizer,
    // A task list ends before a line that is neither indented nor a list item.
    tokenize: (src, tokens, lexer) => {
      const end = src.search(/\n[^\s*+-]/);
      return taskListTokenizer.tokenize(end < 0 ? src : src.slice(0, end + 1), tokens, lexer);
    },
  },
});

const tableStart = Table.config.markdownTokenizer!.start as (src: string) => number;
const BoundedTable = Table.extend({
  markdownTokenizer: {
    ...Table.config.markdownTokenizer!,
    // It reads the first two lines.
    start: (src) => {
      const second = src.indexOf("\n");
      const end = second < 0 ? -1 : src.indexOf("\n", second + 1);
      return tableStart(end < 0 ? src : src.slice(0, end));
    },
  },
});

/** The schema and the Markdown of a page: the editor and `markdown.ts` both build on exactly this list. */
export const blockExtensions: AnyExtension[] = [
  TextParagraph,
  StarterKit.configure({ paragraph: false, underline: false, link: { openOnClick: false }, dropcursor: { color: "var(--ink)", width: 2 } }),
  BoundedTaskList,
  TodoItem.configure({ nested: true }),
  TableKit.configure({ table: false }),
  BoundedTable.configure({ resizable: false }),
  Toggle,
  DetailsSummary.extend(noMarkdown),
  DetailsContent.extend(noMarkdown),
  Callout,
  PageLink,
  RawInline,
  RawBlock,
];
