import { useEffect, useId, useState, type FormEvent } from "react";
import { useErrorText } from "../../app/errors";
import { useCreateOrganization, useSetOrganizationLogo, type Organization } from "../../data/organizations";
import { locale, useI18n } from "../../i18n";
import { Avatar } from "../../ui/Avatar";
import { Button } from "../../ui/Button";
import { Dialog, DialogClose } from "../../ui/Dialog";
import { Input } from "../../ui/Input";
import { PhotoField } from "../../ui/PhotoField";

// The API refuses a bigger logo too; checked here so a large file is not sent only to be refused.
const LOGO_MAX_BYTES = 2 * 1024 * 1024;

/**
 * Nova organização: a name and, optionally, a logo. `onCreated` runs as soon as it exists, before the logo is sent;
 * a logo that fails keeps the dialog open to try it again without creating a second organization.
 */
export function OrgDialog({ onCreated, onClose }: { onCreated: (org: Organization) => void; onClose: () => void }) {
  const { t, lang } = useI18n();
  const formId = useId();
  const errorText = useErrorText();
  const create = useCreateOrganization();
  const setLogo = useSetOrganizationLogo();
  const [name, setName] = useState("");
  const [logo, setLogoFile] = useState<File | null>(null);
  const [tooBig, setTooBig] = useState<number | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const pending = create.isPending || setLogo.isPending;

  useEffect(() => {
    if (!logo) return setPreview(null);
    const url = URL.createObjectURL(logo);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [logo]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const org = create.data ?? (await create.mutateAsync(name.trim(), { onSuccess: onCreated }));
      if (logo) await setLogo.mutateAsync({ orgId: org.id, file: logo });
      onClose();
    } catch {
      // The failed mutation's error shows below.
    }
  }

  const size = (bytes: number) =>
    new Intl.NumberFormat(locale(lang), { maximumFractionDigits: 1 }).format(bytes / 1024 / 1024);

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={t("organizations.new")}
      description={t("organizations.new.description")}
      footer={
        <>
          <DialogClose asChild>
            <Button variant="quiet">{t("organizations.cancel")}</Button>
          </DialogClose>
          <Button type="submit" form={formId} variant="ink" disabled={pending || name.trim() === ""}>
            {t("organizations.create")}
          </Button>
        </>
      }
    >
      <form id={formId} onSubmit={submit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1.5 text-12 text-text-2">
          {t("organizations.name")}
          <Input autoFocus value={name} disabled={create.isSuccess} onChange={(event) => setName(event.target.value)} />
        </label>
        <div className="flex flex-col gap-1.5 text-12 text-text-2">
          {t("organizations.logo")}
          <PhotoField
            avatar={<Avatar name={name} photo={preview} size={64} square />}
            hasPhoto={logo !== null}
            sending={setLogo.isPending}
            error={
              tooBig !== null
                ? t("settings.photo.tooBig", { size: size(tooBig) })
                : setLogo.error
                  ? errorText(setLogo.error, { validation: t("settings.photo.invalid") })
                  : undefined
            }
            onPick={(file) => {
              setLogo.reset();
              setTooBig(file.size > LOGO_MAX_BYTES ? file.size : null);
              setLogoFile(file.size > LOGO_MAX_BYTES ? null : file);
            }}
            onRemove={() => {
              setLogo.reset();
              setTooBig(null);
              setLogoFile(null);
            }}
          />
        </div>
        {create.isError && (
          <p role="alert" className="m-0 text-12 text-err">
            {t("organizations.error.create")}
          </p>
        )}
      </form>
    </Dialog>
  );
}
