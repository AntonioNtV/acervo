import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useErrorText } from "../../app/errors";
import {
  useLeaveOrganization,
  useMembers,
  useRemoveLogo,
  useSetLogo,
  useUpdateOrganization,
  type Organization,
} from "../../data/orgSettings";
import { locale, useI18n } from "../../i18n";
import { Avatar } from "../../ui/Avatar";
import { Button } from "../../ui/Button";
import { Dialog, DialogClose } from "../../ui/Dialog";
import { PhotoField } from "../../ui/PhotoField";
import { AuthError, AuthField } from "../auth/AuthCard";
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

/** Saved when the field loses focus; emptied, it goes back to the name it had. Read-only for a Membro. */
function Name({ organization, readOnly }: { organization: Organization; readOnly: boolean }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const rename = useUpdateOrganization(organization.id);
  const [name, setName] = useState(organization.name);
  return (
    <AuthField
      label={t("auth.name")}
      value={name}
      readOnly={readOnly}
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

/** Sair da organização; its last Owner sees why they cannot, and must make someone else Owner first. */
function Leave({ organization }: { organization: Organization }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const navigate = useNavigate();
  const leave = useLeaveOrganization(organization.id);
  const owner = organization.my_role === "owner";
  const owners = useMembers(organization.id, owner).data?.filter((member) => member.role === "owner");
  const lastOwner = owner && owners?.length === 1;
  const [confirming, setConfirming] = useState(false);
  return (
    <SettingsSection
      title={t("settings.leave")}
      desc={lastOwner ? t("settings.leave.lastOwner") : t("settings.leave.desc", { name: organization.name })}
      action={{ label: t("settings.leave.action"), onClick: () => setConfirming(true), disabled: lastOwner }}
    >
      <Dialog
        open={confirming}
        onOpenChange={setConfirming}
        title={t("settings.leave.confirm", { name: organization.name })}
        description={t("settings.leave.desc", { name: organization.name })}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="quiet">{t("settings.invite.cancel")}</Button>
            </DialogClose>
            <Button
              variant="ink"
              disabled={leave.isPending}
              // Leaving switches to the Pessoal, which unmounts this page: the promise still lands on Bases.
              onClick={() => void leave.mutateAsync().then(() => navigate("/bases"), () => setConfirming(false))}
            >
              {t("settings.leave.action")}
            </Button>
          </>
        }
      />
      {leave.isError && (
        <div className="pt-3">
          <AuthError>{errorText(leave.error, { last_owner: t("settings.leave.lastOwner") })}</AuthError>
        </div>
      )}
    </SettingsSection>
  );
}

/** `/organizacao/geral`: the organization's logo and name, which only its Owners and Admins change, and Sair. */
export function OrgGeneral() {
  const { t } = useI18n();
  const organization = useOrganization();
  const manager = organization.my_role !== "member";
  return (
    <SettingsPage title={t("settings.org.general")}>
      <SettingsSection title={organization.name}>
        <div className="flex flex-col gap-3 pt-4">
          {manager ? (
            <Logo organization={organization} />
          ) : (
            <Avatar name={organization.name} photo={organization.logo_url} size={64} />
          )}
          <Name key={organization.id} organization={organization} readOnly={!manager} />
        </div>
      </SettingsSection>
      <Leave organization={organization} />
    </SettingsPage>
  );
}
