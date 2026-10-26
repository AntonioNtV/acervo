import { useState } from "react";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { Dialog, DialogClose } from "../../ui/Dialog";
import { AuthError, AuthField } from "../auth/AuthCard";

/**
 * The confirmation of what has no Trash, the account or an organization: what goes and what stays, and the button
 * enabled only once `match` (the email or the name) is typed. `items` undefined while they are still being read.
 */
export function DeleteDialog({
  title,
  items,
  match,
  action,
  pending,
  error,
  onDelete,
  onClose,
}: {
  title: string;
  items: string[] | undefined;
  match: string;
  action: string;
  pending: boolean;
  error?: string;
  onDelete: () => void;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const [typed, setTyped] = useState("");
  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={title}
      description={t("deletion.noTrash")}
      footer={
        <>
          <DialogClose asChild>
            <Button>{t("deletion.cancel")}</Button>
          </DialogClose>
          <Button className="text-err!" disabled={!items || typed.trim() !== match || pending} onClick={onDelete}>
            {action}
          </Button>
        </>
      }
    >
      {items && (
        <ul className="m-0 flex list-disc flex-col gap-1.5 pl-[18px] text-13 text-text-2 marker:text-ghost">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
      <AuthField
        label={t("deletion.confirm", { text: match })}
        autoComplete="off"
        autoFocus
        value={typed}
        onChange={(event) => setTyped(event.target.value)}
      />
      {error && <AuthError>{error}</AuthError>}
    </Dialog>
  );
}
