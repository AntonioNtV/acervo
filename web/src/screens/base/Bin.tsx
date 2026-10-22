import { useState } from "react";
import { useKbTrash, useRestoreNode } from "../../api/queries";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { Dialog, DialogClose } from "../../ui/Dialog";
import { NodeName, useTreeErrorText } from "./names";

function Items({ kbId }: { kbId: string }) {
  const { t } = useI18n();
  const trash = useKbTrash(kbId);
  const restore = useRestoreNode();
  const errorText = useTreeErrorText();
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null);
  const items = trash.data ?? [];
  return (
    <>
      {notice && (
        <p role="status" className={notice.error ? "m-0 text-12 text-err" : "m-0 text-12 text-text-2"}>
          {notice.text}
        </p>
      )}
      {trash.data && items.length === 0 && <p className="m-0 text-text-3">{t("tree.bin.empty")}</p>}
      <ul className="m-0 flex max-h-[360px] list-none flex-col overflow-y-auto p-0">
        {items.map((item) => (
          <li key={item.id} className="flex min-h-11 items-center gap-3 border-t border-line first:border-t-0">
            <span className="flex min-w-0 flex-1 flex-col">
              <NodeName node={item} className="truncate" />
              <span className="truncate text-12 text-text-3">{item.path}</span>
            </span>
            <Button
              size="sm"
              disabled={restore.isPending}
              onClick={() =>
                restore.mutate(item.id, {
                  onSuccess: (node) =>
                    setNotice({ text: t(node.to_root ? "tree.bin.restoredToRoot" : "tree.bin.restored", { name: node.title }) }),
                  onError: (e) => setNotice({ text: errorText(e), error: true }),
                })
              }
            >
              {t("tree.bin.restore")}
            </Button>
          </li>
        ))}
      </ul>
    </>
  );
}

/** The base's "Lixeira": what was trashed on its own, with where it was. */
export function Bin({ kbId }: { kbId: string }) {
  const { t } = useI18n();
  return (
    <Dialog
      title={t("tree.bin.open")}
      trigger={
        <button
          type="button"
          className="flex h-7 cursor-pointer items-center rounded-[6px] border-0 bg-transparent px-2.5 text-13 text-text-3 hover:text-text"
        >
          {t("tree.bin.open")}
        </button>
      }
      footer={
        <DialogClose asChild>
          <Button>{t("tree.bin.close")}</Button>
        </DialogClose>
      }
    >
      <Items kbId={kbId} />
    </Dialog>
  );
}
