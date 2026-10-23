import * as RadixDialog from "@radix-ui/react-dialog";
import { useCallback, useEffect, useId, useState, type KeyboardEvent, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import type { NodeWithPath } from "../../api/client";
import { forgetRecent, readRecentPages } from "../../app/lastPage";
import { useKbs } from "../../data/kbs";
import { useCreateNode, useNode, useSearch } from "../../data/tree";
import { useI18n } from "../../i18n";
import { Icon } from "../../ui/Icon";
import { NodeIcon } from "../../ui/NodeIcon";
import { NodeName, useTreeErrorText } from "../base/names";
import { useCurrent } from "../shell/shell";

const SEARCH_DELAY_MS = 200;
const CREATE = "create";

type Found = Pick<NodeWithPath, "id" | "kb_id" | "kind" | "title" | "icon" | "path">;

type Rows = {
  listId: string;
  active: string | null;
  setSelected: (key: string) => void;
};

function Option({ rows, optionKey, onChoose, children }: { rows: Rows; optionKey: string; onChoose: () => void; children: ReactNode }) {
  return (
    <div
      role="option"
      id={`${rows.listId}-${optionKey}`}
      aria-selected={rows.active === optionKey}
      onMouseMove={() => rows.setSelected(optionKey)}
      onClick={onChoose}
      className="mx-1.5 flex min-h-10 cursor-pointer items-center gap-2.5 rounded-[6px] px-2.5 aria-selected:bg-subtle"
    >
      {children}
    </div>
  );
}

function NodeRow({ rows, node, onOpen }: { rows: Rows; node: Found; onOpen: (node: Found) => void }) {
  const parent = node.path.endsWith(`/${node.title}`) ? node.path.slice(0, -node.title.length - 1) : "";
  return (
    <Option rows={rows} optionKey={node.id} onChoose={() => onOpen(node)}>
      <NodeIcon icon={node.icon} kind={node.kind} className="text-text-2" />
      <NodeName node={node} pageExt={false} className="shrink-0 truncate text-13 text-text" />
      {parent && <span className="min-w-0 truncate text-12 text-text-3">{parent}</span>}
    </Option>
  );
}

/**
 * A recent node as it is now: renamed, it shows the new title; gone or trashed, it leaves the list; moved to another
 * base, it leaves this base's recents for good.
 */
function RecentRow({
  rows,
  kbId,
  nodeId,
  onOpen,
  onGone,
}: {
  rows: Rows;
  kbId: string;
  nodeId: string;
  onOpen: (node: Found) => void;
  onGone: (id: string) => void;
}) {
  const { data: node, error } = useNode(nodeId);
  const moved = node !== undefined && node.kb_id !== kbId;
  const gone = Boolean(error || node?.deleted_at || moved);
  useEffect(() => {
    if (moved) forgetRecent(kbId, nodeId);
    if (gone) onGone(nodeId);
  }, [gone, moved, kbId, nodeId, onGone]);
  if (!node || gone) return null;
  return <NodeRow rows={rows} node={node} onOpen={onOpen} />;
}

/**
 * ⌘K: the titles of the current base (the first base where there is none), recents while nothing is typed, and
 * "Criar página" at the base's root as the last item.
 */
export function SearchPalette({ onClose }: { onClose: () => void }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const errorText = useTreeErrorText();
  const listId = useId();
  const { kbId: currentKbId } = useCurrent();
  const kbs = useKbs().data;
  const kbId = currentKbId ?? kbs?.[0]?.id;
  const kbName = kbs?.find((kb) => kb.id === kbId)?.name;
  const [recent] = useState(() => (kbId ? readRecentPages(kbId) : []));
  const [gone, setGone] = useState<ReadonlySet<string>>(new Set());
  const [query, setQuery] = useState("");
  const [searched, setSearched] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  // Enter pressed while the search for what is typed is on its way: it acts once that search answers.
  const [waiting, setWaiting] = useState(false);
  const found = useSearch(kbId ?? "", searched).data;
  const create = useCreateNode(kbId ?? "");
  const title = query.trim();
  const results = title && searched ? found : undefined;
  // What is shown may still be the answer to what was typed before.
  const pending = Boolean(title) && (searched !== title || found === undefined);

  useEffect(() => {
    const timer = setTimeout(() => setSearched(title), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [title]);

  const onGone = useCallback((id: string) => setGone((ids) => new Set(ids).add(id)), []);

  const keys = title
    ? [...(results ?? []).map((node) => node.id), ...(kbId ? [CREATE] : [])]
    : recent.filter((id) => !gone.has(id));
  // Until the person picks a row, the first: new results take over from "Criar página" shown while they loaded.
  const active = selected && keys.includes(selected) ? selected : (keys[0] ?? null);

  const open = (node: Pick<Found, "id" | "kb_id">) => {
    onClose();
    navigate(`/kbs/${node.kb_id}/n/${node.id}`);
  };

  const createPage = () => {
    if (!create.isPending) create.mutate({ kind: "page", parent_id: null, title }, { onSuccess: open });
  };

  // Enter does what a click on the active row does: that row holds its node as it is now.
  const choose = useCallback((key: string) => document.getElementById(`${listId}-${key}`)?.click(), [listId]);

  useEffect(() => {
    if (!waiting || pending) return;
    setWaiting(false);
    if (active) choose(active);
  }, [waiting, pending, active, choose]);

  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const at = active ? keys.indexOf(active) : -1;
      const next = keys[Math.min(Math.max(at + (event.key === "ArrowDown" ? 1 : -1), 0), keys.length - 1)];
      if (!next) return;
      setSelected(next);
      document.getElementById(`${listId}-${next}`)?.scrollIntoView?.({ block: "nearest" });
    } else if (event.key === "Enter" && !event.nativeEvent.isComposing) {
      event.preventDefault();
      if (pending) setWaiting(true);
      else if (active) choose(active);
    }
  };

  const rows: Rows = { listId, active, setSelected };

  return (
    <RadixDialog.Root open onOpenChange={(next) => !next && onClose()}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 bg-[color-mix(in_srgb,var(--text)_24%,transparent)]" />
        <RadixDialog.Content
          aria-describedby={undefined}
          className="fixed top-[110px] left-1/2 flex max-h-[min(560px,calc(100vh-140px))] w-[min(640px,calc(100vw-32px))] -translate-x-1/2 flex-col overflow-hidden rounded-[12px] border border-line-2 bg-bg"
        >
          <RadixDialog.Title className="sr-only">{t("search.title")}</RadixDialog.Title>
          <div className="flex h-[52px] shrink-0 items-center gap-2.5 border-b border-line px-4">
            <Icon name="search" className="text-text-3" />
            <input
              role="combobox"
              aria-label={t("search.title")}
              aria-expanded
              aria-controls={listId}
              aria-activedescendant={active ? `${listId}-${active}` : undefined}
              autoComplete="off"
              value={query}
              placeholder={t("search.placeholder")}
              onChange={(event) => {
                setQuery(event.target.value);
                setWaiting(false);
                create.reset();
              }}
              onKeyDown={onKeyDown}
              className="min-w-0 flex-1 border-0 bg-transparent p-0 text-15 text-text outline-none placeholder:text-ghost"
            />
            {kbName && <span className="shrink-0 text-12 text-ghost">{t("search.in", { base: kbName })}</span>}
          </div>
          <div id={listId} role="listbox" aria-label={t("search.title")} className="min-h-0 flex-1 overflow-y-auto pb-1.5">
            {!title && (
              <>
                <div className="px-4 pt-2.5 pb-1 text-12 text-text-3">{t("search.recent")}</div>
                {keys.length === 0 && <p className="m-0 px-4 py-2 text-13 text-text-3">{t("search.recent.none")}</p>}
                {recent.map((id) => (
                  kbId && <RecentRow key={id} rows={rows} kbId={kbId} nodeId={id} onOpen={open} onGone={onGone} />
                ))}
              </>
            )}
            {results && (
              <>
                <div className="px-4 pt-2.5 pb-1 text-12 text-text-3">{t("search.results")}</div>
                {results.length === 0 && <p className="m-0 px-4 py-2 text-13 text-text-3">{t("search.none")}</p>}
                {results.map((node) => (
                  <NodeRow key={node.id} rows={rows} node={node} onOpen={open} />
                ))}
              </>
            )}
            {kbId && title && (
              <Option rows={rows} optionKey={CREATE} onChoose={createPage}>
                <Icon name="plus" className="text-text-2" />
                <span className="truncate text-13 text-text">{t("search.create", { title })}</span>
              </Option>
            )}
            {create.error && <p className="m-0 px-4 py-1 text-12 text-err">{errorText(create.error)}</p>}
          </div>
          <div className="flex shrink-0 flex-wrap justify-between gap-3 border-t border-line px-4 py-2.5 text-12 text-text-3">
            <span>{t("search.hint")}</span>
            <span>{t("search.scope")}</span>
          </div>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
