import { Placeholder } from "@tiptap/extensions";
import { EditorContent, ReactNodeViewRenderer, useEditor, type Editor } from "@tiptap/react";
import { useRef, useState } from "react";
import { useI18n } from "../i18n";
import { BlockHandle, blockAt, type HoveredBlock } from "./BlockHandle";
import { BLOCK_KINDS, findKinds, findPages } from "./blocks";
import { blockExtensions, PageLink, Toggle } from "./extensions";
import { bindSource, parseMarkdown, serializeMarkdown, type Source } from "./markdown";
import { createMenus, MarkdownPaste, type MenuBridge, type MenuState } from "./menus";
import { MenuPopover, type MenuItem } from "./MenuPopover";
import { PageLinkView, ResolveLink, type LinkTarget } from "./PageLinkView";
import "./editor.css";

export type { LinkTarget };

type Props = {
  /** The text it opens with. Uncontrolled: a new page comes in by remounting the editor with a new key. */
  markdown: string;
  /** The whole page as Markdown, after each edit; never on load. */
  onChange: (markdown: string) => void;
  resolveLink: (title: string) => LinkTarget;
  /** Creates a sub-page and resolves to the title it got, which the editor links to. */
  onCreateSubPage: (title: string) => Promise<string>;
  /** The titles the page picker (`[[`, `@`) offers. */
  pageTitles?: string[];
};

const PageLinkWithView = PageLink.extend({ addNodeView: () => ReactNodeViewRenderer(PageLinkView) });

export function BlockEditor({ markdown, onChange, resolveLink, onCreateSubPage, pageTitles = [] }: Props) {
  const { t } = useI18n();
  const [menu, setMenu] = useState<MenuState | null>(null);
  const [active, setActive] = useState(0);
  const [block, setBlock] = useState<HoveredBlock | null>(null);
  const wrapper = useRef<HTMLDivElement>(null);
  const latest = useRef({ onChange, onCreateSubPage, items: [] as MenuItem[], active: 0, pick: (() => {}) as (i: number) => void });
  latest.current.onChange = onChange;
  latest.current.onCreateSubPage = onCreateSubPage;

  const bridge = useRef<MenuBridge>({
    show: (next) => {
      setMenu(next);
      setActive(0);
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
      ...blockExtensions.map((extension) =>
        extension.name === "pageLink"
          ? PageLinkWithView
          : extension.name === "details"
            ? Toggle.configure({
                renderToggleButton: ({ element, isOpen }) =>
                  element.setAttribute("aria-label", t(isOpen ? "editor.toggle.close" : "editor.toggle.open")),
              })
            : extension,
      ),
      Placeholder.configure({ placeholder: t("editor.placeholder") }),
      createMenus(bridge),
      MarkdownPaste,
    ],
    content: opened.doc,
    editorProps: { attributes: { class: "block-editor", "aria-label": t("editor.label") } },
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
    chain.run();
    void latest.current.onCreateSubPage(t("editor.subpage.title")).then((title) => {
      editor.chain().focus().insertContent({ type: "pageLink", attrs: { title } }).run();
    });
  };

  latest.current.items = items;
  latest.current.active = active;
  latest.current.pick = pick;

  return (
    <ResolveLink.Provider value={resolveLink}>
      <div
        ref={wrapper}
        className="relative"
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
      {menu && <MenuPopover items={items} active={active} rect={menu.rect} onPick={pick} onHover={setActive} />}
    </ResolveLink.Provider>
  );
}
