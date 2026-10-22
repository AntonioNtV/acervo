import type { JSONContent } from "@tiptap/core";
import { MarkdownManager } from "@tiptap/markdown";
import type { Node as PmNode, Schema } from "@tiptap/pm/model";
import { blockExtensions } from "./extensions";

// One manager: each one registers its tokenizers on marked's shared instance.
let shared: MarkdownManager | null = null;
const manager = () => (shared ??= new MarkdownManager({ extensions: blockExtensions }));

/** A top-level block as it was written: its text, what separates it from the next, and how many nodes it became. */
type Chunk = { body: string; gap: string; json: JSONContent[] };

/** The Markdown a page opened with, block by block, so an untouched block is written back exactly as it was. */
export type Source = { lead: string; chunks: Chunk[]; nodes: PmNode[][] };

const EMPTY: Source = { lead: "", chunks: [], nodes: [] };

/** Line endings become `\n`: the only change to a page nobody edited. */
const normalize = (markdown: string) => markdown.replace(/\r\n?/g, "\n");

export function parseMarkdown(markdown: string): { doc: JSONContent; source: Source } {
  const text = normalize(markdown);
  const md = manager();
  const tokens = md.instance.lexer(text);
  // A token marked dropped would be lost on save; the whole page then stays one raw block.
  if (tokens.map((token) => token.raw).join("") !== text) {
    const raw = { type: "rawBlock", content: text ? [{ type: "text", text }] : [] };
    return { doc: { type: "doc", content: [raw] }, source: EMPTY };
  }

  let lead = "";
  let pending = "";
  const chunks: Chunk[] = [];
  for (const token of tokens) {
    if (token.type === "space") {
      pending += token.raw;
      continue;
    }
    const [, before = "", body = "", after = ""] = /^(\n*)([\s\S]*?)(\n*)$/.exec(token.raw) ?? [];
    const previous = chunks.at(-1);
    if (previous) previous.gap += pending + before;
    else lead = pending + before;
    pending = "";
    const json = md.parse(body).content ?? [];
    chunks.push({ body, gap: after, json: json.length ? json : [{ type: "rawBlock", content: [{ type: "text", text: body }] }] });
  }
  const last = chunks.at(-1);
  if (last) last.gap += pending;
  const content = chunks.flatMap((chunk) => chunk.json);
  // An empty page still needs a line to write on.
  if (!content.length) content.push({ type: "paragraph" });
  return { doc: { type: "doc", content }, source: { lead, chunks, nodes: [] } };
}

/** Ties each chunk to the nodes it became in `doc`, the document the editor built from `parseMarkdown`. */
export function bindSource(source: Source, doc: PmNode): Source {
  const schema: Schema = doc.type.schema;
  let index = 0;
  const nodes = source.chunks.map((chunk) => {
    const own = chunk.json.map((json) => schema.nodeFromJSON(json));
    const found = own.map((_, k) => doc.maybeChild(index + k));
    const same = own.every((node, k) => found[k]?.eq(node));
    index += own.length;
    return same ? (found as PmNode[]) : own;
  });
  return { ...source, nodes };
}

const isEmptyParagraph = (node: PmNode) => node.type.name === "paragraph" && node.childCount === 0;

/** The chunk whose nodes start `doc` at `index`, the same objects first (untouched blocks keep their identity). */
function chunkAt(source: Source, kids: readonly PmNode[], index: number): number {
  const matches = (nodes: PmNode[], same: (a: PmNode, b: PmNode) => boolean) =>
    nodes.length > 0 && nodes.every((node, k) => kids[index + k] !== undefined && same(kids[index + k]!, node));
  const byIdentity = source.nodes.findIndex((nodes) => matches(nodes, (a, b) => a === b));
  return byIdentity >= 0 ? byIdentity : source.nodes.findIndex((nodes) => matches(nodes, (a, b) => a.eq(b)));
}

/**
 * The Markdown of `doc`. A block that still equals one the page opened with is written as it was; an edited block
 * is written in the canonical style (`-` bullets, `**` bold, ATX headings, fenced code, one blank line between
 * blocks). Empty paragraphs at the top level are not written.
 */
export function serializeMarkdown(doc: PmNode, source: Source): string {
  const kids: PmNode[] = [];
  doc.forEach((node) => kids.push(node));
  const pieces: Array<{ body: string; chunk: number }> = [];
  for (let i = 0; i < kids.length; ) {
    const chunk = chunkAt(source, kids, i);
    if (chunk >= 0) {
      pieces.push({ body: source.chunks[chunk]!.body, chunk });
      i += source.nodes[chunk]!.length;
      continue;
    }
    const node = kids[i]!;
    i += 1;
    if (isEmptyParagraph(node)) continue;
    // One node at a time: a table, for one, comes out wrapped in blank lines of its own.
    const body = manager().serialize({ type: "doc", content: [node.toJSON()] }).replace(/^\n+|\n+$/g, "");
    if (body.trim()) pieces.push({ body, chunk: -1 });
  }

  if (!pieces.length) return "";
  const lastChunk = source.chunks.length - 1;
  let out = pieces[0]!.chunk === 0 ? source.lead : "";
  pieces.forEach((piece, k) => {
    const previous = pieces[k - 1];
    if (previous) {
      const adjacent = previous.chunk >= 0 && piece.chunk === previous.chunk + 1;
      out += adjacent ? source.chunks[previous.chunk]!.gap : "\n\n";
    }
    out += piece.body;
  });
  const last = pieces.at(-1)!;
  return out + (last.chunk >= 0 && last.chunk === lastChunk ? source.chunks[lastChunk]!.gap : "\n");
}

/** Markdown read as fresh content (a paste): no source to keep. */
export function markdownToJSON(markdown: string): JSONContent {
  return parseMarkdown(markdown).doc;
}
