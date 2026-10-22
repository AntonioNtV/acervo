import { useState, type FormEvent } from "react";
import { useI18n } from "../i18n";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { Input } from "../ui/Input";

type Props = {
  open: boolean;
  incorrect: boolean;
  onSubmit: (password: string) => void;
  onCancel: () => void;
};

/** The password goes to pdf.js only; it lives in this field's state until submitted. */
export function PasswordDialog({ open, incorrect, onSubmit, onCancel }: Props) {
  const { t } = useI18n();
  const [password, setPassword] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    onSubmit(password);
    setPassword("");
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => !next && onCancel()}
      title={t("pdf.password.title")}
      description={t("pdf.password.description")}
    >
      <form onSubmit={submit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1.5">
          <span className="text-12 text-text-2">{t("pdf.password.label")}</span>
          <Input
            type="password"
            autoFocus
            autoComplete="off"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            aria-invalid={incorrect || undefined}
          />
          {incorrect && <span className="text-12 text-err">{t("pdf.password.incorrect")}</span>}
        </label>
        <div className="flex justify-end gap-1.5">
          <Button variant="quiet" onClick={onCancel}>
            {t("pdf.password.cancel")}
          </Button>
          <Button type="submit" variant="ink" disabled={password === ""}>
            {t("pdf.password.open")}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
