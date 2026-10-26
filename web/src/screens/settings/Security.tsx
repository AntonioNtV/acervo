import { useState, type ReactNode } from "react";
import { useErrorText } from "../../app/errors";
import { useMe, type Account } from "../../data/account";
import { useOrganizations } from "../../data/organizations";
import {
  needsReauth,
  useAddPasskey,
  useConfirmTwoFactor,
  useDisableTwoFactor,
  usePasskeys,
  useRemovePasskey,
  useRenamePasskey,
  useSetPassword,
  useStartTwoFactor,
  useUnlinkGoogle,
  type Passkey,
} from "../../data/security";
import { locale, useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { CodeInput } from "../../ui/CodeInput";
import { Dialog, DialogClose } from "../../ui/Dialog";
import { Input } from "../../ui/Input";
import { PasswordField } from "../../ui/PasswordField";
import { e164, PhoneField, type Phone } from "../../ui/PhoneField";
import { SecurityMethodRow } from "../../ui/SecurityMethodRow";
import { relativeTime } from "../bases/when";
import { mask } from "../auth/TwoFactor";
import { useReauth, usePasskeyError } from "./ReauthDialog";
import { SettingsPage, SettingsSection } from "./SettingsFrame";

type Ask = ReturnType<typeof useReauth>["ask"];

/** A failed change's text under its section; a refusal for lack of a recent sign-in is the dialog's, not shown here. */
function Failure({ error, known }: { error: unknown; known?: Partial<Record<string, string>> }) {
  const errorText = useErrorText();
  if (!error || needsReauth(error)) return null;
  return (
    <p role="alert" className="m-0 pt-2 text-12 text-err">
      {errorText(error, known)}
    </p>
  );
}

/** The number for WhatsApp, then the code it got; WhatsApp is on once the code is right. */
export function WhatsAppForm({ onDone, onSent, cancel }: { onDone: () => void; onSent?: (sent: boolean) => void; cancel?: ReactNode }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const start = useStartTwoFactor();
  const confirm = useConfirmTwoFactor();
  const [phone, setPhone] = useState<Phone>({ country: "55", digits: "" });
  const [sent, setSent] = useState(false);
  const [code, setCode] = useState("");
  const number = e164(phone);

  const back = (to: boolean) => {
    setSent(to);
    onSent?.(to);
  };
  if (sent)
    return (
      <CodeInput
        value={code}
        onChange={(value) => {
          setCode(value);
          if (confirm.isError) confirm.reset();
        }}
        onComplete={(value) => confirm.mutate(value, { onSuccess: onDone })}
        sent={t("security.whatsapp.sent", { last: phone.digits.slice(-4) })}
        checking={confirm.isPending}
        error={confirm.isError ? errorText(confirm.error) : undefined}
        footer={
          <Button
            variant="quiet"
            size="sm"
            className="-ml-2 font-normal"
            onClick={() => {
              setCode("");
              confirm.reset();
              back(false);
            }}
          >
            {t("security.whatsapp.change")}
          </Button>
        }
      />
    );
  return (
    <form
      className="m-0 flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (number) start.mutate({ method: "whatsapp", phone: number }, { onSuccess: () => back(true) });
      }}
    >
      <PhoneField
        value={phone}
        onChange={(value) => {
          setPhone(value);
          if (start.isError) start.reset();
        }}
        error={start.isError ? errorText(start.error, { validation: t("security.phone.invalid") }) : undefined}
      />
      <Button type="submit" variant="ink" disabled={!number || start.isPending}>
        {t("security.whatsapp.send")}
      </Button>
      {cancel}
    </form>
  );
}

/** Sets a password, or changes it; every other session ends. */
function PasswordDialog({ account, ask, onClose }: { account: Account; ask: Ask; onClose: () => void }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const save = useSetPassword();
  const [password, setPassword] = useState("");
  const submit = () => save.mutate(password, { onSuccess: onClose, onError: (error) => ask(error, submit) });
  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={t(account.has_password ? "security.password.change" : "security.password.create")}
      description={t("auth.newPassword.desc")}
      footer={
        <>
          <DialogClose asChild>
            <Button>{t("security.cancel")}</Button>
          </DialogClose>
          <Button type="submit" form="security-password" variant="ink" disabled={!password || save.isPending}>
            {t("security.save")}
          </Button>
        </>
      }
    >
      <form
        id="security-password"
        className="m-0"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <PasswordField
          label={t("security.password.new")}
          autoComplete="new-password"
          autoFocus
          hint={t("auth.password.hint")}
          value={password}
          onChange={(event) => {
            setPassword(event.target.value);
            if (save.isError) save.reset();
          }}
          error={save.isError && !needsReauth(save.error) ? errorText(save.error) : undefined}
        />
      </form>
    </Dialog>
  );
}

function RenameDialog({ passkey, onClose }: { passkey: Passkey; onClose: () => void }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const rename = useRenamePasskey();
  const [name, setName] = useState(passkey.name);
  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={t("security.passkey.rename")}
      footer={
        <>
          <DialogClose asChild>
            <Button>{t("security.cancel")}</Button>
          </DialogClose>
          <Button type="submit" form="security-rename" variant="ink" disabled={!name.trim() || rename.isPending}>
            {t("security.save")}
          </Button>
        </>
      }
    >
      <form
        id="security-rename"
        className="m-0 flex flex-col gap-1.5"
        onSubmit={(event) => {
          event.preventDefault();
          rename.mutate({ id: passkey.id, name: name.trim() }, { onSuccess: onClose });
        }}
      >
        <Input aria-label={t("security.passkey.name")} autoFocus value={name} onChange={(event) => setName(event.target.value)} />
        {rename.isError && (
          <span role="alert" className="text-12 text-err">
            {errorText(rename.error)}
          </span>
        )}
      </form>
    </Dialog>
  );
}

function SignInMethods({ account, ask }: { account: Account; ask: Ask }) {
  const { t } = useI18n();
  const unlink = useUnlinkGoogle();
  const [editing, setEditing] = useState(false);
  const doUnlink = () => unlink.mutate(undefined, { onError: (error) => ask(error, doUnlink) });
  return (
    <SettingsSection title={t("security.ways")} desc={t("security.ways.desc")}>
      <SecurityMethodRow
        icon="lock"
        name={t("auth.password")}
        detail={t(account.has_password ? "security.password.detail" : "security.notSet")}
        on={account.has_password}
      >
        <Button size="sm" onClick={() => setEditing(true)}>
          {t(account.has_password ? "security.change" : "security.password.create")}
        </Button>
      </SecurityMethodRow>
      <SecurityMethodRow
        icon="google"
        name="Google"
        detail={account.has_google ? account.email : t("security.google.detail")}
        on={account.has_google}
      >
        {account.has_google && (
          <Button size="sm" variant="quiet" disabled={unlink.isPending} onClick={doUnlink}>
            {t("security.google.unlink")}
          </Button>
        )}
      </SecurityMethodRow>
      <Failure error={unlink.error} known={{ last_way_in: t("security.lastWayIn") }} />
      {editing && <PasswordDialog account={account} ask={ask} onClose={() => setEditing(false)} />}
    </SettingsSection>
  );
}

function Passkeys({ ask }: { ask: Ask }) {
  const { t, lang } = useI18n();
  const passkeyError = usePasskeyError();
  const passkeys = usePasskeys().data;
  const add = useAddPasskey();
  const remove = useRemovePasskey();
  const [renaming, setRenaming] = useState<Passkey | null>(null);
  const doRemove = (id: string) => remove.mutate(id, { onError: (error) => ask(error, () => doRemove(id)) });
  const date = (iso: string) => new Date(iso).toLocaleDateString(locale(lang), { day: "numeric", month: "long" });
  return (
    <SettingsSection
      title={t("security.passkeys")}
      desc={t("security.passkeys.desc")}
      action={{ label: add.isPending ? t("security.waiting") : t("security.passkey.add"), onClick: () => add.mutate(), disabled: add.isPending }}
    >
      {passkeys?.length === 0 && <p className="m-0 border-b border-line py-4 text-13 text-text-3">{t("security.passkeys.none")}</p>}
      {passkeys?.map((passkey) => (
        <SecurityMethodRow
          key={passkey.id}
          icon="passkey"
          name={passkey.name}
          detail={t(passkey.last_used_at ? "security.passkey.detail" : "security.passkey.detail.unused", {
            created: date(passkey.created_at),
            used: passkey.last_used_at ? relativeTime(passkey.last_used_at, lang) : "",
          })}
          on
        >
          <Button size="sm" variant="quiet" onClick={() => setRenaming(passkey)}>
            {t("security.passkey.renameShort")}
          </Button>
          <Button size="sm" variant="quiet" disabled={remove.isPending} onClick={() => doRemove(passkey.id)}>
            {t("security.remove")}
          </Button>
        </SecurityMethodRow>
      ))}
      {passkeyError(add.error) && (
        <p role="alert" className="m-0 pt-2 text-12 text-err">
          {passkeyError(add.error)}
        </p>
      )}
      <Failure error={remove.error} known={{ last_way_in: t("security.lastWayIn") }} />
      {renaming && <RenameDialog passkey={renaming} onClose={() => setRenaming(null)} />}
    </SettingsSection>
  );
}

function TwoFactor({ account, ask }: { account: Account; ask: Ask }) {
  const { t } = useI18n();
  const start = useStartTwoFactor();
  const disable = useDisableTwoFactor();
  const [whatsapp, setWhatsapp] = useState(false);
  const doDisable = () => disable.mutate(undefined, { onError: (error) => ask(error, doDisable) });
  const action = (method: "email" | "whatsapp", turnOn: () => void) =>
    account.two_factor === method ? (
      <Button size="sm" variant="quiet" disabled={disable.isPending} onClick={doDisable}>
        {t("security.disable")}
      </Button>
    ) : (
      <Button size="sm" disabled={start.isPending} onClick={turnOn}>
        {t("security.enable")}
      </Button>
    );
  return (
    <SettingsSection title={t("security.twoFactor")} desc={t("security.twoFactor.desc")}>
      <SecurityMethodRow
        icon="chat"
        name="WhatsApp"
        detail={t(account.two_factor === "whatsapp" ? "security.whatsapp.detail" : "security.notSet")}
        on={account.two_factor === "whatsapp"}
      >
        {action("whatsapp", () => setWhatsapp(true))}
      </SecurityMethodRow>
      {whatsapp && account.two_factor !== "whatsapp" && (
        <div className="w-80 max-w-full border-b border-line py-4">
          <WhatsAppForm
            onDone={() => setWhatsapp(false)}
            cancel={
              <Button variant="quiet" onClick={() => setWhatsapp(false)}>
                {t("security.cancel")}
              </Button>
            }
          />
        </div>
      )}
      <SecurityMethodRow
        icon="mail"
        name={t("auth.email")}
        detail={account.two_factor === "email" ? mask(account.email) : t("security.notSet")}
        on={account.two_factor === "email"}
      >
        {action("email", () => start.mutate({ method: "email" }))}
      </SecurityMethodRow>
      <Failure error={start.error ?? disable.error} />
    </SettingsSection>
  );
}

/** `/conta/seguranca`: how the person signs in, their passkeys and two-step verification. */
export function Security() {
  const { t } = useI18n();
  const account = useMe().data;
  const requiring = useOrganizations().data?.find((organization) => organization.require_two_factor);
  const reauth = useReauth();
  if (!account) return null;
  return (
    <SettingsPage title={t("security.title")}>
      {requiring && account.two_factor === "none" && !account.has_passkey && (
        <p role="status" className="m-0 flex items-baseline gap-2 text-13 text-text-2">
          <span aria-hidden="true" className="size-1.5 shrink-0 -translate-y-px rounded-full bg-warn" />
          {t("security.required", { organization: requiring.name })}
        </p>
      )}
      <SignInMethods account={account} ask={reauth.ask} />
      <Passkeys ask={reauth.ask} />
      <TwoFactor account={account} ask={reauth.ask} />
      {reauth.dialog}
    </SettingsPage>
  );
}
