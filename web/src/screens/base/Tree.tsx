import { createContext, useContext, useEffect, useRef, useState, type DragEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { TreeNode } from "../../api/client";
import {
  useChildren,
  useCreateNode,
  useMoveNode,
  useNode,
  useRenameNode,
  useTrashNode,
} from "../../data/tree";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { cx } from "../../ui/cx";
import { Input } from "../../ui/Input";
import { Menu, MenuItem, MenuSeparator } from "../../ui/Menu";
import { NodeName, useTreeErrorText } from "./names";
import { useStartUpload } from "./Upload";

const NODE_TYPE = "application/x-acervo-node";

type Draft = { parentId: string | null; kind: "folder" | "page" };
type Drop = { id: string; zone: "before" | "into" };

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
  if (!ctx) throw new Error("useTree outside Tree");
  return ctx;
}

/** Opens each folder above `nodeId`, so a node opened from the search or a link shows in the tree. */
function Reveal({ nodeId }: { nodeId: string }) {
  const { setOpen } = useTree();
  const parentId = useNode(nodeId).data?.parent_id;
  useEffect(() => {
    if (parentId) setOpen(parentId, true);
  }, [parentId, setOpen]);
  return parentId ? <Reveal nodeId={parentId} /> : null;
}

export function Tree({ kbId, selectedId }: { kbId: string; selectedId?: string }) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const [draft, setDraftState] = useState<Draft | null>(null);
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

  const setDraft = (next: Draft | null) => {
    if (next?.parentId) setOpen(next.parentId, true);
    setDraftState(next);
  };

  const state: TreeState = {
    kbId,
    selectedId,
    expanded,
    setOpen,
    draft,
    setDraft,
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
    const nodeId = event.dataTransfer.getData(NODE_TYPE);
    if (nodeId) move.mutate({ nodeId, parent_id: null, before_id: null }, { onError: (e) => setNotice(errorText(e)) });
  };

  return (
    <TreeContext.Provider value={state}>
      {selectedId && <Reveal key={selectedId} nodeId={selectedId} />}
      <div className="flex items-center justify-end px-1">
        <Menu
          trigger={
            <Button variant="quiet" size="sm">
              {t("base.new")}
            </Button>
          }
        >
          <MenuItem onSelect={() => setDraft({ parentId: null, kind: "folder" })}>{t("base.new.folder")}</MenuItem>
          <MenuItem onSelect={() => setDraft({ parentId: null, kind: "page" })}>{t("base.new.page")}</MenuItem>
        </Menu>
      </div>
      {notice && (
        <p role="alert" className="m-0 px-2.5 py-1 text-12 text-err">
          {notice}
        </p>
      )}
      <div
        className={cx("flex min-h-12 flex-1 flex-col rounded-[6px]", rootDrop && "bg-muted")}
        onDragOver={(event) => {
          event.preventDefault();
          setRootDrop(true);
        }}
        onDragLeave={() => setRootDrop(false)}
        onDrop={dropOnRoot}
      >
        <ul role="tree" aria-label={t("app.base.tree")} className="m-0 flex list-none flex-col gap-px p-0">
          <Level parentId={null} depth={0} />
        </ul>
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

const indent = (depth: number, leaf: boolean) => ({ paddingLeft: 10 + depth * 16 + (leaf ? 18 : 0) });

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
    <div className="flex flex-col gap-0.5 py-0.5 pr-1">
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
    <li role="none" style={indent(depth, draft.kind === "page")}>
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
  const { kbId, selectedId, expanded, setOpen, editingId, setEditingId, setDraft, setNotice } = tree;
  const { errorText, rename, trash, move, startUpload } = tree;
  const [renameError, setRenameError] = useState<string | null>(null);
  const [drop, setDrop] = useState<Drop["zone"] | null>(null);
  const folder = node.kind === "folder";
  const open = folder && expanded.has(node.id);
  const selected = node.id === selectedId;
  const name = node.title;
  const parentForNew = folder ? node.id : node.parent_id;

  const zoneOf = (event: DragEvent<HTMLElement>): Drop["zone"] => {
    if (!folder) return "before";
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
    const nodeId = event.dataTransfer.getData(NODE_TYPE);
    if (!nodeId || nodeId === node.id) return;
    move.mutate({ nodeId, ...target }, { onError: (e) => setNotice(errorText(e)) });
  };

  let label: ReactNode;
  if (editingId === node.id) {
    label = (
      <div className="flex-1">
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
      </div>
    );
  } else {
    label = (
      <Link
        to={`/kbs/${kbId}/n/${node.id}`}
        onClick={() => folder && setOpen(node.id, true)}
        className={cx(
          "flex h-7 min-w-0 flex-1 items-center no-underline",
          selected ? "text-text" : folder ? "text-text-2 hover:text-text" : "text-text-3 hover:text-text",
        )}
      >
        <NodeName node={node} className="truncate" />
      </Link>
    );
  }

  return (
    <li role="treeitem" aria-expanded={folder ? open : undefined} aria-selected={selected} aria-label={name}>
      <div
        draggable={editingId !== node.id}
        onDragStart={(event) => {
          event.dataTransfer.setData(NODE_TYPE, node.id);
          event.dataTransfer.effectAllowed = "move";
        }}
        onDragOver={(event) => {
          event.preventDefault();
          event.stopPropagation();
          setDrop(zoneOf(event));
        }}
        onDragLeave={() => setDrop(null)}
        onDrop={onDrop}
        style={indent(depth, !folder)}
        className={cx(
          "group flex items-center gap-1.5 rounded-[6px] pr-1",
          selected && "bg-muted",
          drop === "into" && "bg-muted",
          drop === "before" && "shadow-[inset_0_1px_0_var(--text-3)]",
        )}
      >
        {folder && (
          <button
            type="button"
            aria-label={t(open ? "base.collapse" : "base.expand", { name })}
            onClick={() => setOpen(node.id, !open)}
            className="flex size-3 shrink-0 cursor-pointer items-center justify-center border-0 bg-transparent p-0 text-text-3"
          >
            <svg viewBox="0 0 24 24" width={12} height={12} aria-hidden="true" className="fill-none stroke-current stroke-[1.5]">
              <path d={open ? "m6 9 6 6 6-6" : "m9 6 6 6-6 6"} />
            </svg>
          </button>
        )}
        {label}
        <Menu
          trigger={
            <Button
              variant="quiet"
              size="sm"
              icon
              aria-label={t("base.actions", { name })}
              className="opacity-0 group-focus-within:opacity-100 group-hover:opacity-100 data-[state=open]:opacity-100"
            >
              <svg viewBox="0 0 24 24" width={15} height={15} aria-hidden="true" className="fill-current">
                <circle cx="5" cy="12" r="1.3" />
                <circle cx="12" cy="12" r="1.3" />
                <circle cx="19" cy="12" r="1.3" />
              </svg>
            </Button>
          }
        >
          <MenuItem onSelect={() => setDraft({ parentId: parentForNew, kind: "folder" })}>{t("base.new.folder")}</MenuItem>
          <MenuItem onSelect={() => setDraft({ parentId: parentForNew, kind: "page" })}>{t("base.new.page")}</MenuItem>
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
