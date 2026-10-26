import type { AnyExtension } from "@tiptap/core";
import { Placeholder } from "@tiptap/extensions";
import { TextSelection, type Transaction } from "@tiptap/pm/state";
import type { EditorView } from "@tiptap/pm/view";
import { EditorContent, ReactNodeViewRenderer, useEditor, type Editor } from "@tiptap/react";
import { useContext, useEffect, useRef, useState } from "react";
import { useI18n } from "../i18n";
import { BlockHandle, blockAt, measureBlock, type HoveredBlock } from "./BlockHandle";
import { BLOCK_KINDS, findKinds, findPages } from "./blocks";
import { blockExtensions, PageLink, Toggle } from "./extensions";
import { bindSource, parseMarkdown, serializeMarkdown, type Source } from "./markdown";
import { createMenus, MarkdownPaste, type MenuBridge, type MenuState } from "./menus";
import { MenuPopover, type MenuItem } from "./MenuPopover";
import { Emoji } from "./nodes/emoji";
import { PageContext } from "./nodes/generated";
import { insertAttachment } from "./nodes/image";
import { LinkBlockWithView } from "./nodes/linkBlock";
import { PdfPageWithView } from "./nodes/pdfPage";
import { SelectionToolbar } from "./nodes/SelectionToolbar";
import { SyncedBlockWithView } from "./nodes/synced";
import { ToggleHeading } from "./nodes/toggleHeading";
import { PageLinkView, ResolveLink, type LinkTarget } from "./PageLinkView";
import "./editor.css";

export type { LinkTarget };

type Props = {
  /** The text it opens with. Uncontrolled: a new page comes in by remounting the editor with a new key. */
  markdown: string;
  /** The whole page as Markdown, after each edit; never on load. */
  onChange: (markdown: string) => void;
  resolveLink: (title: string) => LinkTarget;
  /** Creates a sub-page and resolves to the title it got, which the editor links to; the caller says why it failed. */
  onCreateSubPage: () => Promise<string>;
  /** The titles the page picker (`[[`, `@`) offers for what is typed after it. */
  pageTitles?: string[];
  /** What is typed after `[[` or `@` while the picker is open; null once it closes. */
  onPageQuery?: (query: string | null) => void;
};

/** Uploads `files` as attachments of the page at the selection; false when there is nothing to take. */
function attach(view: EditorView, files: File[], pageId: string | null) {
  if (!files.length || !pageId) return false;
  insertAttachment((view.dom as HTMLElement & { editor: Editor }).editor, files, pageId);
  return true;
}

const PageLinkWithView = PageLink.extend({ addNodeView: () => ReactNodeViewRenderer(PageLinkView) });

// The nodes whose view needs React, swapped in for the schema's own.
const WITH_VIEW: Record<string, AnyExtension> = {
  pageLink: PageLinkWithView,
  syncedBlock: SyncedBlockWithView,
  pdfPage: PdfPageWithView,
  linkBlock: LinkBlockWithView,
};

export function BlockEditor({ markdown, onChange, resolveLink, onCreateSubPage, pageTitles = [], onPageQuery }: Props) {
  const { t } = useI18n();
  const pageId = useContext(PageContext)?.nodeId ?? null;
  const [menu, setMenu] = useState<MenuState | null>(null);
  const [active, setActive] = useState(0);
  const [block, setBlock] = useState<HoveredBlock | null>(null);
  const wrapper = useRef<HTMLDivElement>(null);
  const latest = useRef({
    pageId,
    onChange,
    onCreateSubPage,
    onPageQuery,
    items: [] as MenuItem[],
    active: 0,
    pick: (() => {}) as (i: number) => void,
  });
  latest.current.pageId = pageId;
  latest.current.onChange = onChange;
  latest.current.onCreateSubPage = onCreateSubPage;
  latest.current.onPageQuery = onPageQuery;

  const bridge = useRef<MenuBridge>({
    show: (next) => {
      setMenu(next);
      setActive(0);
      latest.current.onPageQuery?.(next?.kind === "page" ? next.query : null);
    },
    key: (event) => {
      const { items, active: current, pick } = latest.current;
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        const step = event.key === "ArrowDown" ? 1 : -1;
        setActive(items.length ? (current + step + items.length) % items.length : 0);
        return true;
      }
      if (event.key === "Enter" && items.length) {
        pick(current);
        return true;
      }
      return false;
    },
  });

  const [opened] = useState(() => parseMarkdown(markdown));
  const source = useRef<Source>(opened.source);
  const written = useRef("");

  const editor = useEditor({
    extensions: [
      ...blockExtensions.map(
        (extension) =>
          WITH_VIEW[extension.name] ??
          (extension.name === "toggleHeading"
            ? ToggleHeading.configure({ t })
            : extension.name === "details"
              ? Toggle.configure({
                  renderToggleButton: ({ element, isOpen }) =>
                    element.setAttribute("aria-label", t(isOpen ? "editor.toggle.close" : "editor.toggle.open")),
                })
              : extension),
      ),
      Emoji,
      Placeholder.configure({ placeholder: t("editor.placeholder") }),
      createMenus(bridge),
      MarkdownPaste,
    ],
    content: opened.doc,
    editorProps: {
      attributes: { class: "block-editor", "aria-label": t("editor.label") },
      // The page's top bar (44 px) stays over the text: a line scrolled into view lands below it.
      scrollMargin: { top: 56, bottom: 16, left: 0, right: 0 },
      scrollThreshold: { top: 56, bottom: 16, left: 0, right: 0 },
      // A file pasted or dropped into the page is uploaded as its attachment, where it lands.
      // Rich text that also carries a picture of itself (cells copied from a spreadsheet) pastes as text.
      handlePaste: (view, event) =>
        !event.clipboardData?.types.some((type) => type === "text/html" || type === "text/plain") &&
        attach(view, Array.from(event.clipboardData?.files ?? []), latest.current.pageId),
      handleDrop: (view, event) => {
        const files = Array.from(event.dataTransfer?.files ?? []);
        const at = view.posAtCoords({ left: event.clientX, top: event.clientY });
        if (files.length && at) view.dispatch(view.state.tr.setSelection(TextSelection.near(view.state.doc.resolve(at.pos))));
        return attach(view, files, latest.current.pageId);
      },
    },
    onCreate: ({ editor }) => {
      source.current = bindSource(opened.source, editor.state.doc);
      written.current = serializeMarkdown(editor.state.doc, source.current);
    },
    onUpdate: ({ editor }) => {
      const next = serializeMarkdown(editor.state.doc, source.current);
      // A change that writes the same Markdown (a trailing empty line, a toggle opened) is not an edit.
      if (next === written.current) return;
      written.current = next;
      latest.current.onChange(next);
    },
  });

  // An edit moves blocks: the hovered one is followed to where it went, or let go when it was deleted.
  useEffect(() => {
    if (!editor) return;
    const follow = ({ transaction }: { transaction: Transaction }) => {
      if (!transaction.docChanged) return;
      setBlock((current) => {
        if (!current || !wrapper.current) return current;
        const mapped = transaction.mapping.mapResult(current.pos);
        return mapped.deleted ? null : measureBlock(editor, wrapper.current, mapped.pos);
      });
    };
    editor.on("transaction", follow);
    return () => {
      editor.off("transaction", follow);
    };
  }, [editor]);

  const items: MenuItem[] = !menu
    ? []
    : menu.kind === "slash"
      ? findKinds(menu.query, (kind) => t(`editor.block.${kind.id}`)).map((kind) => ({
          key: kind.id,
          icon: kind.id,
          title: t(`editor.block.${kind.id}`),
          hint: t(`editor.block.${kind.id}.hint`),
          shortcut: kind.shortcut,
          group: t(`editor.menu.${kind.group}`),
        }))
      : findPages(menu.query, pageTitles).map((title) => ({
          key: title,
          icon: "page",
          title,
          group: t("editor.menu.pages"),
        }));

  const pick = (index: number) => {
    const item = items[index];
    if (!editor || !menu || !item) return;
    if (menu.kind === "page") {
      editor
        .chain()
        .focus()
        .deleteRange(menu.range)
        .insertContent([{ type: "pageLink", attrs: { title: item.title } }, { type: "text", text: " " }])
        .run();
      return;
    }
    insertKind(editor, item.key, menu.range);
  };

  const insertKind = (editor: Editor, id: string, range: MenuState["range"]) => {
    const chain = editor.chain().focus().deleteRange(range);
    const kind = BLOCK_KINDS.find((candidate) => candidate.id === id);
    if (kind?.turn) return kind.turn(chain).run();
    if (id === "table") return chain.insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run();
    if (id === "divider") return chain.setHorizontalRule().run();
    if (id === "pageLink") return chain.insertContent("[[").run();
    if (id === "synced") return chain.insertSyncedBlock().run();
    if (id === "inlineEquation") return chain.insertInlineMath().run();
    if (id === "footnote") return chain.insertFootnote().run();
    if (id === "toc") return chain.insertContent({ type: "tableOfContents" }).run();
    if (id === "breadcrumb") return chain.insertContent({ type: "breadcrumb" }).run();
    if (id === "image") return chain.insertImage().run();
    if (id === "file" || id === "video" || id === "audio") return chain.insertAttachmentFile(id).run();
    if (id === "equation") return chain.insertBlockMath().run();
    if (id === "diagram") return chain.insertDiagram().run();
    if (id === "pdfPage") return chain.insertPdfPage().run();
    if (id === "bookmark" || id === "embed") return chain.insertLinkBlock().run();
    chain.run();
    latest.current.onCreateSubPage().then(
      (title) => {
        if (!editor.isDestroyed) editor.chain().focus().insertContent({ type: "pageLink", attrs: { title } }).run();
      },
      () => undefined,
    );
  };

  latest.current.items = items;
  latest.current.active = active;
  latest.current.pick = pick;

  return (
    <ResolveLink.Provider value={resolveLink}>
      <div
        ref={wrapper}
        // The gutter is part of the hover area, so the pointer reaches the handle without leaving it.
        className="relative -ml-14 pl-14"
        onMouseMove={(event) => {
          if (!editor || !wrapper.current) return;
          const hovered = blockAt(editor, wrapper.current, event.target);
          if (hovered && (hovered.pos !== block?.pos || hovered.top !== block?.top)) setBlock(hovered);
        }}
        onMouseLeave={() => setBlock(null)}
      >
        {editor && block && <BlockHandle key={block.pos} editor={editor} block={block} onClose={() => setBlock(null)} />}
        <EditorContent editor={editor} />
      </div>
      {editor && <SelectionToolbar editor={editor} />}
      {menu && <MenuPopover items={items} active={active} rect={menu.rect} onPick={pick} onHover={setActive} />}
    </ResolveLink.Provider>
  );
}
