import { Node } from "@tiptap/core";
import { TextSelection } from "@tiptap/pm/state";
import { NodeViewWrapper, ReactNodeViewRenderer, type ReactNodeViewProps } from "@tiptap/react";
import { useState } from "react";
import { useLinkPreview } from "../../data/linkPreviews";
import { useI18n } from "../../i18n";
import { EmbedFrame, embedOf } from "../../ui/EmbedFrame";
import { LinkPreviewCard } from "../../ui/LinkPreviewCard";
import type { BlockKind } from "../blocks";
import { startBefore } from "../tokenize";
import "./linkBlock.css";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    linkBlock: {
      insertLinkBlock: () => ReturnType;
      /** The block at `pos` back to a paragraph holding its URL as a link. */
      linkBlockToLink: (pos: number) => ReturnType;
    };
  }
}

const URL_TEXT = /^https?:\/\/[^\s<>/]+[^\s<>]*$/;

// A paragraph holding only the URL, bare or as `<url>`: a line after it, or text around it, keeps it a paragraph.
const LINE = /^(?:<(https?:\/\/[^\s<>/]+[^\s<>]*)>|(https?:\/\/[^\s<>/]+[^\s<>]*))[ \t]*(?:\n(?=[ \t]*(?:\n|$))|\n?$)/;

// Not yet given a URL: nothing to write.
const markdownOf = (attrs: Record<string, unknown> | undefined) =>
  attrs?.url ? (attrs.angle ? `<${attrs.url}>` : String(attrs.url)) : "";

/** A URL alone in a paragraph: the site's preview card, or its player for the services EmbedFrame knows. */
export const LinkBlock = Node.create({
  name: "linkBlock",
  group: "block",
  atom: true,
  selectable: true,
  addAttributes: () => ({
    url: { default: "" },
    // Written as `<url>`, so it is written back that way.
    angle: { default: false, rendered: false },
  }),
  parseHTML: () => [
    { tag: "div[data-link-block]", getAttrs: (el) => ({ url: (el as HTMLElement).dataset.linkBlock ?? "" }) },
  ],
  renderHTML: ({ node }) => ["div", { "data-link-block": node.attrs.url, class: "link-block" }, node.attrs.url],
  renderText: ({ node }) => node.attrs.url,
  addCommands() {
    return {
      insertLinkBlock:
        () =>
        ({ commands }) =>
          commands.insertContent({ type: this.name }),
      linkBlockToLink:
        (pos) =>
        ({ state, tr, dispatch }) => {
          const node = state.doc.nodeAt(pos);
          if (node?.type.name !== this.name || !node.attrs.url) return false;
          const { url } = node.attrs;
          const text = state.schema.text(url, [state.schema.marks.link!.create({ href: url })]);
          tr.replaceWith(pos, pos + node.nodeSize, state.schema.nodes.paragraph!.create(null, text));
          // The cursor goes to the link's end, so focusing the editor does not scroll back to the old selection.
          dispatch?.(tr.setSelection(TextSelection.create(tr.doc, pos + 1 + url.length)).scrollIntoView());
          return true;
        },
    };
  },
  markdownTokenizer: {
    name: "linkBlock",
    level: "block",
    start: startBefore(/^<?https?:\/\//m),
    tokenize: (src, tokens) => {
      // Only the page's own list carries `links` (marked's top level): a list item must start with a paragraph.
      // shortcut: a URL alone inside a quote, callout or column stays a link too; tell them apart if one is asked for.
      const match = "links" in tokens ? LINE.exec(src) : null;
      return match
        ? { type: "linkBlock", raw: match[0], url: match[1] ?? match[2], angle: Boolean(match[1]) }
        : undefined;
    },
  },
  parseMarkdown: (token, h) => h.createNode("linkBlock", { url: token.url, angle: token.angle }),
  renderMarkdown: (node) => markdownOf(node.attrs),
});

const domainOf = (url: string) => new URL(url).hostname.replace(/^www\./, "");

function Preview({ url }: { url: string }) {
  const preview = useLinkPreview(url);
  const data = preview.data;
  // A site that did not answer comes back with only its domain.
  const state = preview.isPending ? "loading" : data?.title ? "done" : "failed";
  return (
    <LinkPreviewCard
      url={url}
      state={state}
      title={data?.title ?? undefined}
      description={data?.description ?? undefined}
      domain={data?.domain ?? domainOf(url)}
      image={data?.image ?? undefined}
    />
  );
}

/** The address, until one is pasted. */
function Ask({ onUrl }: { onUrl: (url: string) => void }) {
  const { t } = useI18n();
  const [value, setValue] = useState("");
  const url = value.trim();
  return (
    <input
      autoFocus
      type="url"
      aria-label={t("editor.link.url")}
      placeholder={t("editor.link.url")}
      value={value}
      onChange={(event) => setValue(event.target.value)}
      onKeyDown={(event) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        if (URL_TEXT.test(url)) onUrl(url);
      }}
      className="link-block-ask"
    />
  );
}

export function LinkBlockView({ node, updateAttributes }: ReactNodeViewProps) {
  const url = String(node.attrs.url);
  const embed = url ? embedOf(url) : null;
  return (
    <NodeViewWrapper contentEditable={false} data-link-block-view="">
      {!url ? (
        <Ask onUrl={(given) => updateAttributes({ url: given })} />
      ) : embed ? (
        <EmbedFrame provider={embed.provider} src={embed.src ?? ""} url={url} blocked={!embed.src} />
      ) : (
        <Preview url={url} />
      )}
    </NodeViewWrapper>
  );
}

/** For `BlockEditor`, as `PageLink` gets its view there; `LinkBlock` goes after `RawInline`/`RawBlock`. */
export const LinkBlockWithView = LinkBlock.extend({
  addNodeView: () =>
    ReactNodeViewRenderer(LinkBlockView, {
      // The editor would select the block on mousedown and swallow the click that opens the site and the input.
      stopEvent: ({ event }) => event.target instanceof Element && event.target.closest("a, input, iframe") !== null,
    }),
});

/** Both inserted with `insertLinkBlock()`: the block asks for the address, and its URL decides preview or player. */
export const linkBlockKinds: BlockKind[] = [
  { id: "bookmark", group: "link" },
  { id: "embed", group: "link" },
];
