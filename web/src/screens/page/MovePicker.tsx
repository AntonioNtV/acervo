import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import type { NodeDetail } from "../../api/client";
import { useKbs } from "../../data/kbs";
import { ApiError } from "../../data/request";
import { useDebouncedSearch, useMoveNode } from "../../data/tree";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { Dialog, DialogClose } from "../../ui/Dialog";
import { Input } from "../../ui/Input";
import { folderPath } from "../../ui/names";
import { NodeIcon } from "../../ui/NodeIcon";
import { useTreeErrorText } from "../base/names";

const rowClass =
  "flex min-h-8 w-full min-w-0 cursor-pointer items-center gap-2 rounded-[6px] border-0 bg-transparent px-2 text-left font-[inherit] text-13 text-text hover:bg-subtle disabled:cursor-default";

/**
 * One base as a destination: `root` (its root's row), then its folders and pages whose title holds `query`, but
 * `skip` (the node being moved).
 */
export function Destinations({
  kbId,
  root,
  query,
  skip,
  onPick,
  busy = false,
}: {
  kbId: string;
  root: ReactNode;
  query: string;
  skip?: string;
  onPick: (parentId: string | null, path: string) => void;
  busy?: boolean;
}) {
  const { searched, found = [] } = useDebouncedSearch(kbId, query);
  const places = searched ? found.filter((hit) => hit.kind !== "file" && hit.id !== skip) : [];
  return (
    <li className="flex flex-col gap-px">
      <button type="button" disabled={busy} onClick={() => onPick(null, "")} className={rowClass}>
        {root}
      </button>
      {places.map((place) => (
        <button
          key={place.id}
          type="button"
          disabled={busy}
          onClick={() => onPick(place.id, place.path)}
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

  const errorText = (error: unknown) => {
    const files = error instanceof ApiError && error.code === "conflict" ? (error.details.files as string[] | undefined) : undefined;
    return files?.length ? t("page.move.held", { files: files.join(", ") }) : treeErrorText(error);
  };

  const pick = (kbId: string, parentId: string | null) =>
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
          <Destinations
            key={kb.id}
            kbId={kb.id}
            root={
              <>
                <span className="text-text-3">
                  <NodeIcon icon={kb.icon} kind="bases" />
                </span>
                <span className="truncate font-medium">{kb.name}</span>
              </>
            }
            query={query}
            skip={node.id}
            onPick={(parentId) => pick(kb.id, parentId)}
            busy={move.isPending}
          />
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
