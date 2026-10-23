import { useEffect, useState } from "react";
import { useSearch } from "../../data/tree";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { Dialog, DialogClose } from "../../ui/Dialog";
import { Input } from "../../ui/Input";
import { folderPath } from "../../ui/names";
import { NodeIcon } from "../../ui/NodeIcon";

const SEARCH_DELAY_MS = 200;

const rowClass =
  "flex min-h-8 w-full min-w-0 cursor-pointer items-center gap-2 rounded-[6px] border-0 bg-transparent px-2 text-left font-[inherit] text-13 text-text hover:bg-subtle";

export type Place = { nodeId: string | null; path: string };

/** "Escolher outra pasta…": the base's root, then its folders and pages whose title holds what is typed. */
export function FolderPicker({ kbId, onPick, onClose }: { kbId: string; onPick: (place: Place) => void; onClose: () => void }) {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [searched, setSearched] = useState("");
  const found = useSearch(kbId, searched).data ?? [];

  useEffect(() => {
    const timer = setTimeout(() => setSearched(query.trim()), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [query]);

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={t("chat.picker.title")}
      footer={
        <DialogClose asChild>
          <Button>{t("chat.cancel")}</Button>
        </DialogClose>
      }
    >
      <Input
        autoFocus
        aria-label={t("chat.picker.search")}
        placeholder={t("chat.picker.search")}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      <ul className="m-0 -mx-2 flex max-h-[320px] list-none flex-col gap-px overflow-y-auto p-0">
        <li>
          <button type="button" className={rowClass} onClick={() => onPick({ nodeId: null, path: "" })}>
            <span className="truncate font-medium">{t("chat.root")}</span>
          </button>
        </li>
        {found
          .filter((hit) => hit.kind !== "file")
          .map((hit) => (
            <li key={hit.id}>
              <button type="button" className={rowClass} onClick={() => onPick({ nodeId: hit.id, path: hit.path })}>
                <span className="text-text-3">
                  <NodeIcon icon={hit.icon} kind={hit.kind} />
                </span>
                <span className="shrink-0 truncate">{hit.title}</span>
                <span className="min-w-0 truncate text-12 text-ghost">{folderPath(hit.path, hit.title)}</span>
              </button>
            </li>
          ))}
      </ul>
    </Dialog>
  );
}
