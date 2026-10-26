import { useState } from "react";
import { useErrorText } from "../../app/errors";
import { useRemoveLogo, useSetLogo, useUpdateOrganization, type Organization } from "../../data/orgSettings";
import { locale, useI18n } from "../../i18n";
import { Avatar } from "../../ui/Avatar";
import { PhotoField } from "../../ui/PhotoField";
import { AuthField } from "../auth/AuthCard";
import { SettingsPage, SettingsSection, useOrganization } from "./SettingsFrame";

// The API refuses a bigger logo too; checked here so a large file is not sent only to be refused.
const LOGO_MAX_BYTES = 2 * 1024 * 1024;

function Logo({ organization }: { organization: Organization }) {
  const { t, lang } = useI18n();
  const errorText = useErrorText();
  const upload = useSetLogo(organization.id);
  const remove = useRemoveLogo(organization.id);
  const [tooBig, setTooBig] = useState<number | null>(null);
  const failed = upload.error ?? remove.error;
  const size = (bytes: number) =>
    new Intl.NumberFormat(locale(lang), { maximumFractionDigits: 1 }).format(bytes / 1024 / 1024);

  return (
    <PhotoField
      kind="logo"
      avatar={<Avatar name={organization.name} photo={organization.logo_url} size={64} />}
      hasPhoto={organization.logo_url !== null}
      sending={upload.isPending}
      error={
        tooBig !== null
          ? t("settings.photo.tooBig", { size: size(tooBig) })
          : failed
            ? errorText(failed, { validation: t("settings.photo.invalid") })
            : undefined
      }
      onPick={(file) => {
        remove.reset();
        upload.reset();
        setTooBig(file.size > LOGO_MAX_BYTES ? file.size : null);
        if (file.size <= LOGO_MAX_BYTES) upload.mutate(file);
      }}
      onRemove={() => {
        upload.reset();
        setTooBig(null);
        remove.mutate();
      }}
    />
  );
}

/** Saved when the field loses focus; emptied, it goes back to the name it had. */
function Name({ organization }: { organization: Organization }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const rename = useUpdateOrganization(organization.id);
  const [name, setName] = useState(organization.name);
  return (
    <AuthField
      label={t("auth.name")}
      value={name}
      onChange={(event) => setName(event.target.value)}
      onKeyDown={(event) => event.key === "Enter" && event.currentTarget.blur()}
      onBlur={() => {
        const next = name.trim();
        if (!next) setName(organization.name);
        else if (next !== organization.name) rename.mutate({ name: next });
      }}
      error={rename.isError ? errorText(rename.error) : undefined}
    />
  );
}

/** `/organizacao/geral`: the organization's logo and name. */
export function OrgGeneral() {
  const { t } = useI18n();
  const organization = useOrganization();
  return (
    <SettingsPage title={t("settings.org.general")}>
      <SettingsSection title={organization.name}>
        <div className="flex flex-col gap-3 pt-4">
          <Logo organization={organization} />
          <Name key={organization.id} organization={organization} />
        </div>
      </SettingsSection>
    </SettingsPage>
  );
}
