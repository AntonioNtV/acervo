import { useState } from "react";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { Dialog, DialogClose } from "../../ui/Dialog";
import { Input } from "../../ui/Input";
import { Destinations } from "../page/MovePicker";

export type Place = { nodeId: string | null; path: string };

/** "Escolher outra pasta…": the base's root, then its folders and pages whose title holds what is typed. */
export function FolderPicker({ kbId, onPick, onClose }: { kbId: string; onPick: (place: Place) => void; onClose: () => void }) {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
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
      <ul className="m-0 -mx-2 flex max-h-[320px] list-none flex-col overflow-y-auto p-0">
        <Destinations
          kbId={kbId}
          root={<span className="truncate font-medium">{t("chat.root")}</span>}
          query={query}
          onPick={(nodeId, path) => onPick({ nodeId, path })}
        />
      </ul>
    </Dialog>
  );
}
