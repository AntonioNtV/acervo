import type { Editor } from "@tiptap/core";
import { NodeSelection, TextSelection } from "@tiptap/pm/state";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { useI18n } from "../i18n";
import { BLOCK_KINDS, type BlockKind } from "./blocks";
import { Icon } from "./icons";

/**
 * The block under the pointer, top-level or in a column: where it starts in the document and where it sits in the
 * wrapper. `left` is set only in a column, whose blocks do not start at the page's edge.
 */
export type HoveredBlock = { pos: number; top: number; left?: number };

const isColumn = (el: HTMLElement | null) => el?.hasAttribute("data-column") ?? false;

/** The block holding `target`, top-level or in a column, measured against `wrapper`; null outside the text. */
export function blockAt(editor: Editor, wrapper: HTMLElement, target: EventTarget | null): HoveredBlock | null {
  const root = editor.view.dom;
  let el = target instanceof HTMLElement ? target : null;
  if (!el || !root.contains(el) || el === root) return null;
  while (el.parentElement && el.parentElement !== root && !isColumn(el.parentElement)) el = el.parentElement;
  const { doc } = editor.state;
  const depth = el.parentElement === root ? 0 : doc.resolve(editor.view.posAtDOM(el.parentElement!, 0)).depth;
  const $pos = doc.resolve(editor.view.posAtDOM(el, 0));
  return measureBlock(editor, wrapper, $pos.depth > depth ? $pos.before(depth + 1) : $pos.pos);
}

const HANDLE_HEIGHT = 24;
// The "+" and the grip with the gap between them, so a column's handle ends where its block starts.
const HANDLE_WIDTH = 46;

/**
 * The block starting at `pos`, where it sits now in the wrapper; null when none starts there. `top` places
 * the handle on the middle of the block's first line, whatever the block's padding and line height.
 */
export function measureBlock(editor: Editor, wrapper: HTMLElement, pos: number): HoveredBlock | null {
  const dom = editor.view.nodeDOM(pos);
  if (!(dom instanceof HTMLElement)) return null;
  const style = getComputedStyle(dom);
  const line = parseFloat(style.lineHeight) || HANDLE_HEIGHT;
  const firstLine = (parseFloat(style.paddingTop) || 0) + (parseFloat(style.borderTopWidth) || 0);
  const box = dom.getBoundingClientRect();
  const frame = wrapper.getBoundingClientRect();
  const top = box.top - frame.top + firstLine + (line - HANDLE_HEIGHT) / 2;
  return isColumn(dom.parentElement) ? { pos, top, left: box.left - frame.left - HANDLE_WIDTH } : { pos, top };
}

const itemClass =
  "flex h-[30px] w-full cursor-pointer items-center gap-2 rounded-[6px] border-0 bg-transparent px-2 text-left text-13 text-text hover:bg-subtle";

/** "+" inserts a block below and opens the "/" menu; the grip drags the block or opens its menu. */
export function BlockHandle({ editor, block, onClose }: { editor: Editor; block: HoveredBlock; onClose: () => void }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const menu = useRef<HTMLDivElement>(null);
  const node = editor.state.doc.nodeAt(block.pos);

  useEffect(() => {
    if (!open) return;
    const away = (event: MouseEvent) => {
      if (!menu.current?.contains(event.target as globalThis.Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  if (!node) return null;
  const after = block.pos + node.nodeSize;
  const done = () => {
    setOpen(false);
    onClose();
  };

  const add = () => {
    editor
      .chain()
      .focus()
      .insertContentAt(after, { type: "paragraph", content: [{ type: "text", text: "/" }] })
      .setTextSelection(after + 2)
      .run();
    onClose();
  };

  const turn = (kind: BlockKind) => {
    const relist = kind.list && /List$/.test(node.type.name) ? kind.list : null;
    if (relist === node.type.name) return done();
    const chain = editor
      .chain()
      .focus()
      .command(({ tr }) => {
        const start = tr.doc.resolve(block.pos + 1);
        // A list changes kind as a whole; any other block is selected whole, so all its lines turn.
        tr.setSelection(relist ? TextSelection.near(start) : TextSelection.between(start, tr.doc.resolve(after - 1)));
        return true;
      });
    (relist ? chain.toggleList(relist, relist === "taskList" ? "taskItem" : "listItem") : kind.turn!(chain)).run();
    done();
  };

  const duplicate = () => {
    editor.chain().focus().insertContentAt(after, node.toJSON()).run();
    done();
  };

  const toLink = () => {
    editor.chain().focus().linkBlockToLink(block.pos).run();
    done();
  };

  const remove = () => {
    editor.chain().focus().deleteRange({ from: block.pos, to: after }).run();
    done();
  };

  const dragStart = (event: DragEvent) => {
    const { view } = editor;
    const selection = NodeSelection.create(view.state.doc, block.pos);
    view.dispatch(view.state.tr.setSelection(selection));
    // ProseMirror moves what `view.dragging` holds when it is dropped inside the editor.
    view.dragging = { slice: selection.content(), move: true };
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", node.textContent);
    const dom = view.nodeDOM(block.pos);
    if (dom instanceof HTMLElement) event.dataTransfer.setDragImage(dom, 0, 0);
  };

  return (
    <div className="absolute left-1 flex gap-0.5 text-ghost" style={{ top: block.top, left: block.left }}>
      <button
        type="button"
        aria-label={t("editor.handle.add")}
        onClick={add}
        className="inline-flex h-6 w-[22px] cursor-pointer items-center justify-center rounded-[4px] border-0 bg-transparent p-0 text-ghost hover:bg-subtle"
      >
        <Icon name="plus" size={14} />
      </button>
      <button
        type="button"
        draggable
        aria-label={t("editor.handle.drag")}
        aria-haspopup="menu"
        aria-expanded={open}
        onDragStart={dragStart}
        onDragEnd={onClose}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex h-6 w-[22px] cursor-grab items-center justify-center rounded-[4px] border-0 bg-transparent p-0 text-ghost hover:bg-subtle"
      >
        <Icon name="grip" size={14} />
      </button>
      {open && (
        <div
          ref={menu}
          role="menu"
          className="absolute top-7 left-6 z-30 flex w-[220px] flex-col rounded-[8px] border border-line-2 bg-bg p-1"
        >
          <div className="px-2 pt-1 pb-0.5 text-12 text-text-3">{t("editor.handle.turnInto")}</div>
          {BLOCK_KINDS.filter((kind) => kind.turn).map((kind) => (
            <button key={kind.id} type="button" role="menuitem" className={itemClass} onClick={() => turn(kind)}>
              <span className="text-text-2">
                <Icon name={kind.id} size={14} />
              </span>
              {t(`editor.block.${kind.id}`)}
            </button>
          ))}
          <div className="my-1 h-px bg-line" />
          {node.type.name === "linkBlock" && (
            <button type="button" role="menuitem" className={itemClass} onClick={toLink}>
              {t("editor.link.toLink")}
            </button>
          )}
          <button type="button" role="menuitem" className={itemClass} onClick={duplicate}>
            {t("editor.handle.duplicate")}
          </button>
          <button type="button" role="menuitem" className={itemClass} onClick={remove}>
            {t("editor.handle.delete")}
          </button>
        </div>
      )}
    </div>
  );
}
