import { useState } from "react";
import { useErrorText } from "../../app/errors";
import {
  useConfirmEmailChange,
  useMe,
  useRemovePhoto,
  useRename,
  useRequestEmailChange,
  useSetPhoto,
  type Account,
} from "../../data/account";
import { ApiError } from "../../data/request";
import { locale, useI18n } from "../../i18n";
import { Avatar } from "../../ui/Avatar";
import { Button } from "../../ui/Button";
import { CodeInput } from "../../ui/CodeInput";
import { PasswordField } from "../../ui/PasswordField";
import { PhotoField } from "../../ui/PhotoField";
import { AuthField } from "../auth/AuthCard";
import { SettingsPage, SettingsSection } from "./SettingsFrame";

// The API refuses a bigger photo too; checked here so a large file is not sent only to be refused.
const PHOTO_MAX_BYTES = 2 * 1024 * 1024;

function Photo({ account }: { account: Account }) {
  const { t, lang } = useI18n();
  const errorText = useErrorText();
  const upload = useSetPhoto();
  const remove = useRemovePhoto();
  const [tooBig, setTooBig] = useState<number | null>(null);
  const failed = upload.error ?? remove.error;
  const size = (bytes: number) =>
    new Intl.NumberFormat(locale(lang), { maximumFractionDigits: 1 }).format(bytes / 1024 / 1024);

  return (
    <PhotoField
      avatar={<Avatar name={account.name} email={account.email} photo={account.photo_url} size={64} />}
      hasPhoto={account.photo_url !== null}
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
        setTooBig(file.size > PHOTO_MAX_BYTES ? file.size : null);
        if (file.size <= PHOTO_MAX_BYTES) upload.mutate(file);
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
function Name({ account }: { account: Account }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const rename = useRename();
  const [name, setName] = useState(account.name);
  return (
    <AuthField
      label={t("auth.name")}
      placeholder={t("auth.name.placeholder")}
      autoComplete="name"
      value={name}
      onChange={(event) => setName(event.target.value)}
      onKeyDown={(event) => event.key === "Enter" && event.currentTarget.blur()}
      onBlur={() => {
        const next = name.trim();
        if (!next) setName(account.name);
        else if (next !== account.name) rename.mutate(next);
      }}
      error={rename.isError ? errorText(rename.error) : undefined}
    />
  );
}

/** A new address gets a code, after the current password if there is one; the email changes once that code is typed. */
function Email({ account }: { account: Account }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const request = useRequestEmailChange();
  const confirm = useConfirmEmailChange();
  const [email, setEmail] = useState(account.email);
  const [password, setPassword] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [code, setCode] = useState("");

  if (sentTo)
    return (
      <CodeInput
        value={code}
        onChange={(value) => {
          setCode(value);
          if (confirm.isError) confirm.reset();
        }}
        onComplete={(value) =>
          confirm.mutate(value, {
            onSuccess: (changed) => {
              setSentTo(null);
              setCode("");
              setEmail(changed.email);
            },
          })
        }
        sent={t("settings.email.sent", { email: sentTo })}
        checking={confirm.isPending}
        error={confirm.isError ? errorText(confirm.error) : undefined}
        footer={
          <Button
            variant="quiet"
            size="sm"
            className="-ml-2 font-normal"
            onClick={() => {
              setSentTo(null);
              setCode("");
              setEmail(account.email);
            }}
          >
            {t("settings.email.cancel")}
          </Button>
        }
      />
    );

  const changed = email.trim() !== account.email;
  const failure = request.error instanceof ApiError ? request.error.code : "";
  return (
    <form
      className="m-0 flex items-start gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        const next = email.trim();
        request.mutate(account.has_password ? { new_email: next, password } : { new_email: next }, {
          onSuccess: () => {
            setSentTo(next);
            setPassword("");
          },
        });
      }}
    >
      <div className="flex flex-1 flex-col gap-3">
        <AuthField
          label={t("auth.email")}
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => {
            setEmail(event.target.value);
            if (request.isError) request.reset();
          }}
          error={
            request.isError && failure !== "invalid_credentials"
              ? errorText(request.error, { too_many_attempts: t("settings.email.wait") })
              : undefined
          }
        />
        {changed && account.has_password && (
          <PasswordField
            label={t("auth.password")}
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
              if (request.isError) request.reset();
            }}
            error={failure === "invalid_credentials" ? t("settings.email.wrongPassword") : undefined}
          />
        )}
      </div>
      {changed && (
        <Button type="submit" disabled={request.isPending || !email.trim()} className="mt-[26px]">
          {t("settings.email.send")}
        </Button>
      )}
    </form>
  );
}

/** `/conta/perfil`: photo, name and email, how other people see the person. */
export function Profile() {
  const { t } = useI18n();
  const account = useMe().data;
  if (!account) return null;
  return (
    <SettingsPage title={t("settings.profile")}>
      <SettingsSection title={t("settings.profile.how")}>
        <div className="flex flex-col gap-3 pt-4">
          <Photo account={account} />
          <Name account={account} />
          <Email account={account} />
        </div>
      </SettingsSection>
    </SettingsPage>
  );
}
