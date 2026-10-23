import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { KbSummary, NodeDetail } from "../../api/client";
import { useKbs } from "../../data/kbs";
import { ApiError } from "../../data/request";
import { useMoveNode, useSearch } from "../../data/tree";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { Dialog, DialogClose } from "../../ui/Dialog";
import { Input } from "../../ui/Input";
import { folderPath } from "../../ui/names";
import { NodeIcon } from "../../ui/NodeIcon";
import { useTreeErrorText } from "../base/names";

const SEARCH_DELAY_MS = 200;

const rowClass =
  "flex min-h-8 w-full min-w-0 cursor-pointer items-center gap-2 rounded-[6px] border-0 bg-transparent px-2 text-left font-[inherit] text-13 text-text hover:bg-subtle disabled:cursor-default";

type Choose = (kbId: string, parentId: string | null) => void;

/** One base as a destination: its root, then its folders and pages whose title holds what is typed. */
function BaseDestinations({
  kb,
  query,
  node,
  onPick,
  busy,
}: {
  kb: KbSummary;
  query: string;
  node: NodeDetail;
  onPick: Choose;
  busy: boolean;
}) {
  const found = useSearch(kb.id, query).data ?? [];
  const places = query ? found.filter((hit) => hit.kind !== "file" && hit.id !== node.id) : [];
  return (
    <li className="flex flex-col gap-px">
      <button type="button" disabled={busy} onClick={() => onPick(kb.id, null)} className={rowClass}>
        <span className="text-text-3">
          <NodeIcon icon={kb.icon} kind="bases" />
        </span>
        <span className="truncate font-medium">{kb.name}</span>
      </button>
      {places.map((place) => (
        <button
          key={place.id}
          type="button"
          disabled={busy}
          onClick={() => onPick(kb.id, place.id)}
          className={rowClass}
          style={{ paddingLeft: 30 }}
        >
          <span className="text-text-3">
            <NodeIcon icon={place.icon} kind={place.kind} />
          </span>
          <span className="shrink-0 truncate">{place.title}</span>
          <span className="min-w-0 truncate text-12 text-ghost">{folderPath(place.path, place.title)}</span>
        </button>
      ))}
    </li>
  );
}

/**
 * "Mover para…": every base's root, and its folders and pages by title. Into another base the sub-pages and files go
 * along; a file the destination already holds refuses the move, naming it.
 */
export function MovePicker({ node, onClose }: { node: NodeDetail; onClose: () => void }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const kbs = useKbs().data ?? [];
  const move = useMoveNode();
  const treeErrorText = useTreeErrorText();
  const [query, setQuery] = useState("");
  const [searched, setSearched] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setSearched(query.trim()), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [query]);

  const errorText = (error: unknown) => {
    const files = error instanceof ApiError && error.code === "conflict" ? (error.details.files as string[] | undefined) : undefined;
    return files?.length ? t("page.move.held", { files: files.join(", ") }) : treeErrorText(error);
  };

  const pick: Choose = (kbId, parentId) =>
    move.mutate(
      { nodeId: node.id, kb_id: kbId, parent_id: parentId, before_id: null },
      {
        onSuccess: () => {
          onClose();
          navigate(`/kbs/${kbId}/n/${node.id}`);
        },
      },
    );

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={t("page.move.title", { name: node.title })}
      footer={
        <DialogClose asChild>
          <Button>{t("page.move.cancel")}</Button>
        </DialogClose>
      }
    >
      <Input
        autoFocus
        aria-label={t("page.move.search")}
        placeholder={t("page.move.search")}
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          move.reset();
        }}
      />
      <ul className="m-0 -mx-2 flex max-h-[320px] list-none flex-col gap-1 overflow-y-auto p-0">
        {kbs.map((kb) => (
          <BaseDestinations key={kb.id} kb={kb} query={searched} node={node} onPick={pick} busy={move.isPending} />
        ))}
      </ul>
      {move.error && (
        <p role="alert" className="m-0 text-12 text-err">
          {errorText(move.error)}
        </p>
      )}
    </Dialog>
  );
}
