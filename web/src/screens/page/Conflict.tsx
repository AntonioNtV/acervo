import type { StalePage } from "../../api/client";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { Dialog } from "../../ui/Dialog";
import { DiffLines } from "./DiffLines";

/** "Concluir" on a page that got a newer version: both choices keep every version in the history. */
export function Conflict({
  stale,
  busy,
  onKeepMine,
  onDiscard,
  onClose,
}: {
  stale: StalePage | null;
  busy: boolean;
  onKeepMine: () => void;
  onDiscard: () => void;
  onClose: () => void;
}) {
  const { t } = useI18n();
  return (
    <Dialog
      open={stale !== null}
      onOpenChange={(open) => !open && onClose()}
      title={t("page.conflict.title")}
      description={t("page.conflict.description")}
      footer={
        <>
          <Button variant="quiet" onClick={onDiscard} disabled={busy}>
            {t("page.conflict.discard")}
          </Button>
          <Button variant="ink" onClick={onKeepMine} disabled={busy}>
            {t("page.conflict.keep")}
          </Button>
        </>
      }
    >
      <div className="max-h-[50vh] overflow-y-auto rounded-[7px] border border-line">
        {stale && <DiffLines lines={stale.diff} />}
      </div>
    </Dialog>
  );
}
