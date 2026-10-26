import { Node, type JSONContent } from "@tiptap/core";
import type { Node as PmNode } from "@tiptap/pm/model";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { EditorContent, NodeViewWrapper, ReactNodeViewRenderer, useEditor, type ReactNodeViewProps } from "@tiptap/react";
import { useQuery } from "@tanstack/react-query";
import { createContext, lazy, Suspense, useContext } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { normalizeLinkTarget } from "../../data/pages";
import { call } from "../../data/request";
import { useI18n } from "../../i18n";
import { SyncedFrame } from "../../ui/SyncedFrame";
import type { BlockKind } from "../blocks";
import { startBefore } from "../tokenize";
import { PageLinkView, ResolveLink, type LinkTarget } from "../PageLinkView";
import { PageContext } from "./generated";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    syncedBlock: { insertSyncedBlock: () => ReturnType };
  }
}

// A line holding only `![[Title]]` or `![[Title#Section]]`; the server takes the target before the first `#`.
const LINE = /^!\[\[([^[\]#]+)(?:#([^[\]]*))?\]\][ \t]*(?:\n|$)/;


const markdownOf = (attrs: Record<string, unknown> | undefined) =>
  `![[${attrs?.title ?? ""}${attrs?.section == null ? "" : `#${attrs.section}`}]]`;

/** `!` then a picked or typed `[[…]]`, alone in a top-level paragraph: the title and section of a synced block. */
function typedLink(paragraph: PmNode): { title: string; section: string | null } | null {
  const kids: PmNode[] = [];
  paragraph.forEach((kid) => kids.push(kid));
  const [bang, link, rest] = kids;
  if (bang?.text !== "!" || link?.type.name !== "pageLink" || kids.length > 3) return null;
  if (rest && rest.text?.trim() !== "") return null;
  const [title = "", ...section] = String(link.attrs.title).split("#");
  return { title, section: section.length ? section.join("#") : null };
}

/** `![[Page#Section]]`: that `##` section of another page, or the whole page, shown here read-only and current. */
export const SyncedBlock = Node.create({
  name: "syncedBlock",
  group: "block",
  atom: true,
  selectable: true,
  addAttributes: () => ({
    title: { default: "" },
    section: { default: null },
    // Just inserted from the picker: the view asks which section, once.
    choosing: { default: false, rendered: false },
  }),
  parseHTML: () => [
    {
      tag: "div[data-synced]",
      getAttrs: (el) => ({ title: (el as HTMLElement).dataset.synced ?? "", section: (el as HTMLElement).dataset.section ?? null }),
    },
  ],
  renderHTML: ({ node }) => [
    "div",
    { "data-synced": node.attrs.title, "data-section": node.attrs.section, class: "synced-block" },
    markdownOf(node.attrs),
  ],
  renderText: ({ node }) => markdownOf(node.attrs),
  addCommands() {
    return {
      // The page picker opens on `[[`; picking a page after the `!` turns the line into the block.
      insertSyncedBlock:
        () =>
        ({ commands }) =>
          commands.insertContent("![["),
    };
  },
  addProseMirrorPlugins() {
    const type = this.type;
    return [
      new Plugin({
        key: new PluginKey("syncedFromLink"),
        appendTransaction: (transactions, _old, state) => {
          if (!transactions.some((tr) => tr.docChanged)) return null;
          const { $head } = state.selection;
          if ($head.depth !== 1 || $head.parent.type.name !== "paragraph") return null;
          const link = typedLink($head.parent);
          if (!link) return null;
          const node = type.create({ ...link, choosing: link.section === null });
          return state.tr.replaceWith($head.before(), $head.after(), node);
        },
      }),
    ];
  },
  markdownTokenizer: {
    name: "syncedBlock",
    level: "block",
    start: startBefore(/^!\[\[/m),
    tokenize: (src) => {
      const match = LINE.exec(src);
      return match ? { type: "syncedBlock", raw: match[0], title: match[1], section: match[2] ?? null } : undefined;
    },
  },
  parseMarkdown: (token, h) => h.createNode("syncedBlock", { title: token.title, section: token.section }),
  renderMarkdown: (node) => markdownOf(node.attrs),
});

/** Where `![[Title]]` comes from: the page and its address, or why there is none. */
export type SyncedTarget = { nodeId: string; href: string } | "missing" | "ambiguous";

export const SyncedSource = createContext<(title: string) => SyncedTarget>(() => "missing");

// The pages already shown around this block, outermost first: one of them again is a loop.
const Shown = createContext<string[]>([]);

const HEADING = /^## +(.+?)[ #]*$/;

/** The `index`-th `##` section of `markdown`, from its heading to the next `##`; code blocks are skipped as the server does. */
export function cutSection(markdown: string, index: number): string {
  const lines = markdown.split("\n");
  let inCode = false;
  let seen = -1;
  let start = -1;
  for (const [i, line] of lines.entries()) {
    if (/^(```|~~~)/.test(line)) inCode = !inCode;
    if (inCode || !HEADING.test(line)) continue;
    seen += 1;
    if (start >= 0) return lines.slice(start, i).join("\n");
    if (seen === index) start = i;
  }
  return start >= 0 ? lines.slice(start).join("\n") : "";
}

// Imported when first shown: extensions.ts registers `SyncedBlock`, so a static import of it from here is a cycle.
const ReadOnly = lazy(async () => {
  const [{ blockExtensions }, { parseMarkdown }] = await Promise.all([import("../extensions"), import("../markdown")]);
  return {
    default: function ReadOnly({ markdown }: { markdown: string }) {
      const editor = useEditor(
        {
          extensions: blockExtensions.map((extension) =>
            extension.name === "pageLink"
              ? extension.extend({ addNodeView: () => ReactNodeViewRenderer(PageLinkView) })
              : extension.name === "syncedBlock"
                ? SyncedBlockWithView
                : extension,
          ),
          content: parseMarkdown(markdown).doc as JSONContent,
          editable: false,
          editorProps: { attributes: { class: "block-editor" } },
        },
        [markdown],
      );
      return <EditorContent editor={editor} />;
    },
  };
});

export function SyncedBlockView({ node, deleteNode, updateAttributes }: ReactNodeViewProps) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { nodeId: current } = useParams();
  const title = String(node.attrs.title);
  const section = node.attrs.section as string | null;
  const target = useContext(SyncedSource)(title);
  const shownAround = useContext(Shown);
  const host = useContext(PageContext);
  const looped = typeof target === "object" && (target.nodeId === current || shownAround.includes(target.nodeId));
  const source = typeof target === "object" && !looped ? target : null;
  const page = useQuery({
    queryKey: ["node", source?.nodeId ?? "", "page"],
    enabled: source !== null,
    queryFn: () => call(api.GET("/v1/pages/{node_id}", { params: { path: { node_id: source!.nodeId } } })),
  });

  const sections = page.data?.sections ?? [];
  const index = section === null ? -1 : sections.findIndex((s) => normalizeLinkTarget(s.heading) === normalizeLinkTarget(section));
  const error = !source || page.isError || (page.data !== undefined && section !== null && index < 0);
  const shown = page.data && (section === null ? page.data.markdown : cutSection(page.data.markdown, index));

  // Links and synced blocks inside resolve from the source page's own links, at the same base's addresses.
  const linkedId = (linked: string) => page.data?.links[normalizeLinkTarget(linked.split("#")[0]!)] ?? "missing";
  const hrefOf = (id: string) => source!.href.replace(/[^/]+$/, id);
  const resolveLink = (linked: string): LinkTarget => {
    const id = linkedId(linked);
    return id === "missing" || id === "ambiguous" || !source ? "missing" : { href: hrefOf(id) };
  };
  const syncedSource = (linked: string): SyncedTarget => {
    const id = linkedId(linked);
    return id === "missing" || id === "ambiguous" || !source ? "missing" : { nodeId: id, href: hrefOf(id) };
  };

  const choose = (heading: string | null) => updateAttributes({ section: heading, choosing: false });

  return (
    <NodeViewWrapper contentEditable={false} data-synced-view="">
      <SyncedFrame
        source={section === null ? title : `${title} › ${section}`}
        error={error}
        onEdit={() => source && navigate(index >= 0 ? `${source.href}#${sections[index]!.anchor}` : source.href)}
        onUnlink={deleteNode}
      >
        {node.attrs.choosing && page.data ? (
          <ul aria-label={t("editor.block.synced")} className="m-0 flex list-none flex-col p-0">
            {[{ heading: null, label: t("editor.synced.wholePage") }, ...sections.map((s) => ({ heading: s.heading, label: s.heading }))].map(
              (option) => (
                <li key={option.heading ?? ""}>
                  <button
                    type="button"
                    onClick={() => choose(option.heading)}
                    className="flex h-[30px] w-full cursor-pointer items-center rounded-[6px] border-0 bg-transparent px-2.5 text-left text-13 text-text hover:bg-subtle"
                  >
                    {option.label}
                  </button>
                </li>
              ),
            )}
          </ul>
        ) : (
          shown !== undefined && (
            <ResolveLink.Provider value={resolveLink}>
              <SyncedSource.Provider value={syncedSource}>
                <Shown.Provider value={[...shownAround, source!.nodeId]}>
                  <PageContext.Provider value={host && { kbId: host.kbId, nodeId: source!.nodeId }}>
                    <Suspense fallback={null}>
                      <ReadOnly markdown={shown} />
                    </Suspense>
                  </PageContext.Provider>
                </Shown.Provider>
              </SyncedSource.Provider>
            </ResolveLink.Provider>
          )
        )}
      </SyncedFrame>
    </NodeViewWrapper>
  );
}

/** For `BlockEditor`, as `PageLink` gets its view there; `SyncedBlock` alone goes after `RawInline`/`RawBlock`. */
export const SyncedBlockWithView = SyncedBlock.extend({
  addNodeView: () =>
    ReactNodeViewRenderer(SyncedBlockView, {
      // The editor would select the block on mousedown and swallow the click of "Editar na origem" and the section list.
      stopEvent: ({ event }) => event.target instanceof Element && event.target.closest("button") !== null,
    }),
});

/** Inserted with `insertSyncedBlock()`: `![[` opens the page picker, then the block lists the page's sections. */
export const syncedKinds: BlockKind[] = [{ id: "synced", group: "link" }];
