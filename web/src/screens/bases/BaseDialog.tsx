import { useId, useState, type FormEvent } from "react";
import { useCreateKb, useUpdateKb, type KbSummary } from "../../api/queries";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { Dialog, DialogClose } from "../../ui/Dialog";
import { Input } from "../../ui/Input";

export type BaseEdit = { mode: "create" } | { mode: "rename" | "describe"; kb: KbSummary };

/** Creating a base, renaming it or editing its description; closes itself once the API took it. */
export function BaseDialog({ edit, onClose }: { edit: BaseEdit; onClose: () => void }) {
  const { t } = useI18n();
  const formId = useId();
  const kb = edit.mode === "create" ? null : edit.kb;
  const [name, setName] = useState(kb?.name ?? "");
  const [description, setDescription] = useState(kb?.description ?? "");
  const create = useCreateKb();
  const update = useUpdateKb();
  const mutation = edit.mode === "create" ? create : update;
  const showName = edit.mode !== "describe";
  const showDescription = edit.mode !== "rename";

  function submit(event: FormEvent) {
    event.preventDefault();
    const done = { onSuccess: onClose };
    if (edit.mode === "create") create.mutate({ name: name.trim(), description: description.trim() }, done);
    else if (edit.mode === "rename") update.mutate({ kbId: edit.kb.id, name: name.trim() }, done);
    else update.mutate({ kbId: edit.kb.id, description: description.trim() }, done);
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={t(`bases.dialog.${edit.mode}`)}
      footer={
        <>
          <DialogClose asChild>
            <Button variant="quiet">{t("bases.cancel")}</Button>
          </DialogClose>
          <Button
            type="submit"
            form={formId}
            variant="ink"
            disabled={mutation.isPending || (showName && name.trim() === "")}
          >
            {t(edit.mode === "create" ? "bases.create" : "bases.save")}
          </Button>
        </>
      }
    >
      <form id={formId} onSubmit={submit} className="flex flex-col gap-3">
        {showName && (
          <label className="flex flex-col gap-1.5 text-12 text-text-2">
            {t("bases.name")}
            <Input autoFocus value={name} onChange={(event) => setName(event.target.value)} />
          </label>
        )}
        {showDescription && (
          <label className="flex flex-col gap-1.5 text-12 text-text-2">
            {t("bases.description")}
            <Input
              autoFocus={!showName}
              value={description}
              placeholder={t("bases.description.placeholder")}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
        )}
        {mutation.isError && (
          <p role="alert" className="m-0 text-12 text-err">
            {t("bases.error.save")}
          </p>
        )}
      </form>
    </Dialog>
  );
}
