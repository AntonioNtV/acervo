import { createContext, useContext, useEffect, useRef, useState, type DragEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { TreeNode } from "../../api/client";
import { useChildren, useCreateNode, useMoveNode, useNode, useRenameNode, useTrashNode } from "../../data/tree";
import { useI18n } from "../../i18n";
import { cx } from "../../ui/cx";
import { Icon } from "../../ui/Icon";
import { IconButton } from "../../ui/IconButton";
import { Input } from "../../ui/Input";
import { Menu, MenuItem, MenuSeparator } from "../../ui/Menu";
import { NodeName, useTreeErrorText } from "../base/names";
import { useStartUpload } from "../base/Upload";

const NODE_TYPE = "application/x-acervo-node";

export type Draft = { parentId: string | null; kind: "folder" | "page" };
type Zone = "before" | "into";

type TreeState = {
  kbId: string;
  selectedId?: string;
  expanded: Set<string>;
  setOpen: (id: string, open: boolean) => void;
  draft: Draft | null;
  setDraft: (draft: Draft | null) => void;
  editingId: string | null;
  setEditingId: (id: string | null) => void;
  setNotice: (text: string | null) => void;
  errorText: (error: unknown) => string;
  rename: ReturnType<typeof useRenameNode>;
  trash: ReturnType<typeof useTrashNode>;
  move: ReturnType<typeof useMoveNode>;
  startUpload: ReturnType<typeof useStartUpload>;
};

const TreeContext = createContext<TreeState | null>(null);

function useTree(): TreeState {
  const ctx = useContext(TreeContext);
  if (!ctx) throw new Error("useTree outside TreeRows");
  return ctx;
}

/** The node dragged, when it comes from this base: the API moves a node only inside its own base. */
function draggedNode(event: DragEvent, kbId: string): string | null {
  try {
    const dragged = JSON.parse(event.dataTransfer.getData(NODE_TYPE)) as { kbId: string; id: string };
    return dragged.kbId === kbId ? dragged.id : null;
  } catch {
    return null;
  }
}

/** Opens each node above `nodeId`, so a node opened from a link shows in the tree. */
function Reveal({ nodeId }: { nodeId: string }) {
  const { setOpen } = useTree();
  const parentId = useNode(nodeId).data?.parent_id;
  useEffect(() => {
    if (parentId) setOpen(parentId, true);
  }, [parentId, setOpen]);
  return parentId ? <Reveal nodeId={parentId} /> : null;
}

const rowClass =
  "flex h-7 w-full min-w-0 cursor-pointer items-center gap-1.5 rounded-[6px] border-0 bg-transparent pr-1 text-left text-13 no-underline hover:bg-muted";

const indent = (depth: number) => ({ paddingLeft: 8 + depth * 14 });

/** A base's tree in the sidebar: folders and pages open lazily, drag to move, rename inline, drop files to upload. */
export function TreeRows({
  kbId,
  selectedId,
  draft,
  onDraft,
}: {
  kbId: string;
  selectedId?: string;
  draft: Draft | null;
  onDraft: (draft: Draft | null) => void;
}) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [rootDrop, setRootDrop] = useState(false);
  // Created once here: every row calls these.
  const rename = useRenameNode();
  const trash = useTrashNode();
  const move = useMoveNode();
  const startUpload = useStartUpload(kbId);
  const errorText = useTreeErrorText();

  const [setOpen] = useState(() => (id: string, open: boolean) =>
    setExpanded((current) => {
      if (current.has(id) === open) return current;
      const next = new Set(current);
      if (open) next.add(id);
      else next.delete(id);
      return next;
    }),
  );

  useEffect(() => {
    if (draft?.parentId) setOpen(draft.parentId, true);
  }, [draft, setOpen]);

  const state: TreeState = {
    kbId,
    selectedId,
    expanded,
    setOpen,
    draft,
    setDraft: onDraft,
    editingId,
    setEditingId,
    setNotice,
    errorText,
    rename,
    trash,
    move,
    startUpload,
  };

  const dropOnRoot = (event: DragEvent) => {
    event.preventDefault();
    setRootDrop(false);
    setNotice(null);
    if (event.dataTransfer.files.length) return startUpload(Array.from(event.dataTransfer.files), null);
    const nodeId = draggedNode(event, kbId);
    if (nodeId) move.mutate({ nodeId, parent_id: null, before_id: null }, { onError: (e) => setNotice(errorText(e)) });
  };

  return (
    <TreeContext.Provider value={state}>
      {selectedId && <Reveal key={selectedId} nodeId={selectedId} />}
      {notice && (
        <p role="alert" className="m-0 px-2 py-1 text-12 text-err">
          {notice}
        </p>
      )}
      <div
        className={cx("flex flex-col gap-px rounded-[6px]", rootDrop && "bg-muted")}
        onDragOver={(event) => {
          event.preventDefault();
          setRootDrop(true);
        }}
        onDragLeave={() => setRootDrop(false)}
        onDrop={dropOnRoot}
      >
        <ul role="tree" aria-label={t("shell.tree")} className="m-0 flex list-none flex-col gap-px p-0">
          <Level parentId={null} depth={0} />
        </ul>
        <button
          type="button"
          onClick={() => onDraft({ parentId: null, kind: "page" })}
          className={cx(rowClass, "text-text-3")}
          style={indent(0)}
        >
          <span className="size-4 shrink-0" />
          <Icon name="plus" size={14} />
          <span className="truncate">{t("base.new.page")}</span>
        </button>
      </div>
    </TreeContext.Provider>
  );
}

function Level({ parentId, depth }: { parentId: string | null; depth: number }) {
  const { kbId, draft } = useTree();
  const children = useChildren(kbId, parentId).data ?? [];
  return (
    <>
      {draft && draft.parentId === parentId && <DraftRow draft={draft} depth={depth} />}
      {children.map((node) => (
        <Row key={node.id} node={node} depth={depth} />
      ))}
    </>
  );
}

function NameInput({
  initial,
  label,
  onSubmit,
  onCancel,
  error,
}: {
  initial: string;
  label: string;
  onSubmit: (title: string) => void;
  onCancel: () => void;
  error: string | null;
}) {
  const [value, setValue] = useState(initial);
  const input = useRef<HTMLInputElement>(null);
  // The menu that opened this hands focus back to its trigger on close; take it after that.
  useEffect(() => {
    const id = setTimeout(() => input.current?.focus());
    return () => clearTimeout(id);
  }, []);
  return (
    <div className="flex min-w-0 flex-1 flex-col gap-0.5 py-0.5 pr-1">
      <Input
        ref={input}
        aria-label={label}
        aria-invalid={error ? true : undefined}
        className="h-[26px]"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onFocus={(event) => event.target.select()}
        onKeyDown={(event) => {
          if (event.key === "Escape") onCancel();
          if (event.key === "Enter" && value.trim()) onSubmit(value.trim());
        }}
      />
      {error && (
        <span role="alert" className="text-12 text-err">
          {error}
        </span>
      )}
    </div>
  );
}

function DraftRow({ draft, depth }: { draft: Draft; depth: number }) {
  const { t } = useI18n();
  const { kbId, setDraft, errorText } = useTree();
  const create = useCreateNode(kbId);
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  return (
    <li role="none" className="flex items-start gap-1.5" style={indent(depth)}>
      <span className="size-4 shrink-0" />
      <NameInput
        initial=""
        label={t(draft.kind === "folder" ? "base.new.folder" : "base.new.page")}
        error={error}
        onCancel={() => setDraft(null)}
        onSubmit={(title) =>
          create.mutate(
            { parent_id: draft.parentId, kind: draft.kind, title },
            {
              onSuccess: (node) => {
                setDraft(null);
                navigate(`/kbs/${kbId}/n/${node.id}`);
              },
              onError: (e) => setError(errorText(e)),
            },
          )
        }
      />
    </li>
  );
}

function Row({ node, depth }: { node: TreeNode; depth: number }) {
  const { t } = useI18n();
  const tree = useTree();
  const { kbId, selectedId, expanded, setOpen, editingId, setEditingId, draft, setDraft, setNotice } = tree;
  const { errorText, rename, trash, move, startUpload } = tree;
  const [renameError, setRenameError] = useState<string | null>(null);
  const [drop, setDrop] = useState<Zone | null>(null);
  const folder = node.kind === "folder";
  const page = node.kind === "page";
  const hasCaret = folder || (page && (node.has_children || draft?.parentId === node.id));
  const open = hasCaret && expanded.has(node.id);
  const selected = node.id === selectedId;
  const name = node.title;
  const parentForNew = folder || page ? node.id : node.parent_id;

  const zoneOf = (event: DragEvent<HTMLElement>): Zone => {
    if (!folder && !page) return "before";
    const box = event.currentTarget.getBoundingClientRect();
    return event.clientY - box.top < box.height / 3 ? "before" : "into";
  };

  const onDrop = (event: DragEvent<HTMLElement>) => {
    event.preventDefault();
    event.stopPropagation();
    const zone = zoneOf(event);
    setDrop(null);
    setNotice(null);
    const target = zone === "into" ? { parent_id: node.id, before_id: null } : { parent_id: node.parent_id, before_id: node.id };
    if (event.dataTransfer.files.length) return startUpload(Array.from(event.dataTransfer.files), target.parent_id);
    const nodeId = draggedNode(event, kbId);
    if (!nodeId || nodeId === node.id) return;
    move.mutate({ nodeId, ...target }, { onError: (e) => setNotice(errorText(e)) });
  };

  let label: ReactNode;
  if (editingId === node.id) {
    label = (
      <NameInput
        initial={name}
        label={t("base.rename")}
        error={renameError}
        onCancel={() => {
          setRenameError(null);
          setEditingId(null);
        }}
        onSubmit={(title) =>
          title === name
            ? setEditingId(null)
            : rename.mutate(
                { nodeId: node.id, title },
                { onSuccess: () => setEditingId(null), onError: (e) => setRenameError(errorText(e)) },
              )
        }
      />
    );
  } else {
    label = (
      <Link
        to={`/kbs/${kbId}/n/${node.id}`}
        onClick={() => hasCaret && setOpen(node.id, true)}
        className={cx("flex h-7 min-w-0 flex-1 items-center gap-1.5 no-underline", selected ? "text-text" : "text-text-2")}
      >
        <Icon name={node.kind} size={14} />
        <NodeName node={node} pageExt={false} className="truncate" />
      </Link>
    );
  }

  return (
    <li role="treeitem" aria-expanded={hasCaret ? open : undefined} aria-selected={selected} aria-label={name}>
      <div
        draggable={editingId !== node.id}
        onDragStart={(event) => {
          event.dataTransfer.setData(NODE_TYPE, JSON.stringify({ kbId, id: node.id }));
          event.dataTransfer.effectAllowed = "move";
        }}
        onDragOver={(event) => {
          event.preventDefault();
          event.stopPropagation();
          setDrop(zoneOf(event));
        }}
        onDragLeave={() => setDrop(null)}
        onDrop={onDrop}
        style={indent(depth)}
        className={cx(
          "group flex min-h-7 items-center gap-1.5 rounded-[6px] pr-1 hover:bg-muted",
          (selected || drop === "into") && "bg-muted",
          selected && "font-medium",
          drop === "before" && "shadow-[inset_0_1px_0_var(--text-3)]",
        )}
      >
        {hasCaret ? (
          <button
            type="button"
            aria-label={t(open ? "base.collapse" : "base.expand", { name })}
            onClick={() => setOpen(node.id, !open)}
            className="flex size-4 shrink-0 cursor-pointer items-center justify-center border-0 bg-transparent p-0 text-ghost hover:text-text"
          >
            <Icon name={open ? "caretDown" : "caretRight"} size={14} />
          </button>
        ) : (
          <span className="size-4 shrink-0" />
        )}
        {label}
        <Menu
          trigger={
            <IconButton
              size="sm"
              aria-label={t("base.actions", { name })}
              className="opacity-0 group-focus-within:opacity-100 group-hover:opacity-100 data-[state=open]:opacity-100"
            >
              <Icon name="more" size={14} />
            </IconButton>
          }
        >
          <MenuItem onSelect={() => setDraft({ parentId: parentForNew, kind: "page" })}>{t("base.new.page")}</MenuItem>
          {folder && (
            <MenuItem onSelect={() => setDraft({ parentId: node.id, kind: "folder" })}>{t("base.new.folder")}</MenuItem>
          )}
          <MenuSeparator />
          <MenuItem onSelect={() => setEditingId(node.id)}>{t("base.rename")}</MenuItem>
          <MenuItem onSelect={() => trash.mutate(node.id, { onError: (e) => setNotice(errorText(e)) })}>
            {t("base.trash")}
          </MenuItem>
        </Menu>
      </div>
      {open && (
        <ul role="group" className="m-0 flex list-none flex-col gap-px p-0">
          <Level parentId={node.id} depth={depth + 1} />
        </ul>
      )}
    </li>
  );
}
