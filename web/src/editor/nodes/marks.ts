import { Mark } from "@tiptap/core";
import type { TextColor } from "../../ui/ColorMenu";
import "./marks.css";

export const TEXT_COLORS: TextColor[] = ["gray", "brown", "orange", "yellow", "green", "blue", "pink", "red"];

const UNDERLINE = /^<u>([\s\S]+?)<\/u>/;
// No space right inside the `==`, so "a == b" stays text.
const HIGHLIGHT = /^==(?=\S)([\s\S]*?\S)==/;
// Any other color is left to RawInline, which keeps it as written.
const TEXT_COLOR = new RegExp(`^<span data-color="(${TEXT_COLORS.join("|")})">([\\s\\S]+?)</span>`);

/** `<u>…</u>`: Markdown has no underline, and the tag renders everywhere. */
export const Underline = Mark.create({
  name: "underline",
  parseHTML: () => [{ tag: "u" }],
  renderHTML: () => ["u", 0],
  addKeyboardShortcuts() {
    return { "Mod-u": () => this.editor.commands.toggleMark(this.name) };
  },
  markdownTokenizer: {
    name: "underline",
    level: "inline",
    start: (src) => src.indexOf("<u>"),
    tokenize: (src, _tokens, lexer) => {
      const match = UNDERLINE.exec(src);
      return match ? { type: "underline", raw: match[0], tokens: lexer.inlineTokens(match[1]!) } : undefined;
    },
  },
  parseMarkdown: (token, h) => h.applyMark("underline", h.parseInline(token.tokens ?? [])),
  renderMarkdown: (node, h) => `<u>${h.renderChildren(node)}</u>`,
});

/** `==…==`, the highlight of Obsidian and other Markdown editors. */
export const Highlight = Mark.create({
  name: "highlight",
  parseHTML: () => [{ tag: "mark" }],
  renderHTML: () => ["mark", 0],
  markdownTokenizer: {
    name: "highlight",
    level: "inline",
    start: (src) => src.indexOf("=="),
    tokenize: (src, _tokens, lexer) => {
      const match = HIGHLIGHT.exec(src);
      return match ? { type: "highlight", raw: match[0], tokens: lexer.inlineTokens(match[1]!) } : undefined;
    },
  },
  parseMarkdown: (token, h) => h.applyMark("highlight", h.parseInline(token.tokens ?? [])),
  renderMarkdown: (node, h) => `==${h.renderChildren(node)}==`,
});

/** `<span data-color="blue">…</span>`, one of the eight text colors. */
export const TextColorMark = Mark.create({
  name: "textColor",
  addAttributes: () => ({ color: { default: "gray" } }),
  parseHTML: () => [{ tag: "span[data-color]", getAttrs: (el) => ({ color: (el as HTMLElement).dataset.color }) }],
  renderHTML: ({ mark }) => [
    "span",
    { "data-color": mark.attrs.color, style: `color: var(--tc-${mark.attrs.color})` },
    0,
  ],
  markdownTokenizer: {
    name: "textColor",
    level: "inline",
    start: (src) => src.indexOf("<span data-color="),
    tokenize: (src, _tokens, lexer) => {
      const match = TEXT_COLOR.exec(src);
      return match
        ? { type: "textColor", raw: match[0], color: match[1], tokens: lexer.inlineTokens(match[2]!) }
        : undefined;
    },
  },
  parseMarkdown: (token, h) => h.applyMark("textColor", h.parseInline(token.tokens ?? []), { color: token.color }),
  renderMarkdown: (node, h) => `<span data-color="${node.attrs?.color}">${h.renderChildren(node)}</span>`,
});

// After `blockExtensions`: marked tries the tokenizer registered last first, and these must win over RawInline.
export const markExtensions = [Underline, Highlight, TextColorMark];
