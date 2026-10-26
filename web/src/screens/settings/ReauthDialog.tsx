import { useQueryClient } from "@tanstack/react-query";
import { useId, useState, type ReactNode } from "react";
import { useErrorText } from "../../app/errors";
import { useMe } from "../../data/account";
import { ApiError } from "../../data/request";
import { needsReauth, useReauthenticate, usePasskeySignIn } from "../../data/security";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { Dialog, DialogClose } from "../../ui/Dialog";
import { PasswordField } from "../../ui/PasswordField";
import { GoogleLogo, PasskeyLogo, ProviderButton } from "../../ui/ProviderButton";
import { cancelled } from "../../webauthn";

/** What a failed passkey prompt says; nothing when the person closed the browser's prompt. */
export function usePasskeyError() {
  const { t } = useI18n();
  const errorText = useErrorText();
  return (error: unknown): string | undefined => {
    if (!error || cancelled(error) || needsReauth(error)) return undefined;
    if (!(error instanceof ApiError)) return t("security.passkey.failed");
    return errorText(error, {
      invalid_credentials: t("security.passkey.failed"),
      code_invalid: t("security.passkey.expired"),
    });
  };
}

/**
 * For the sensitive changes (password, 2FA off or by WhatsApp, adding or removing a passkey, unlinking Google, the
 * email): `ask` in a change's `onError` opens the dialog when the API wants a recent sign-in, and runs `retry` once
 * the person confirmed.
 */
export function useReauth(): { ask: (error: unknown, retry: () => void) => void; dialog: ReactNode } {
  const [retry, setRetry] = useState<(() => void) | null>(null);
  return {
    ask: (error, again) => {
      if (needsReauth(error)) setRetry(() => again);
    },
    dialog: retry && (
      <ReauthDialog
        onClose={() => setRetry(null)}
        onConfirmed={() => {
          setRetry(null);
          retry();
        }}
      />
    ),
  };
}

/** The password, or a passkey, again; an account with neither signs in with Google again and comes back here. */
function ReauthDialog({ onConfirmed, onClose }: { onConfirmed: () => void; onClose: () => void }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const passkeyError = usePasskeyError();
  const queryClient = useQueryClient();
  const formId = useId();
  const account = useMe().data;
  const [password, setPassword] = useState("");
  const reauthenticate = useReauthenticate();
  const passkey = usePasskeySignIn();
  if (!account) return null;

  const withPasskey = () =>
    passkey.mutate(undefined, {
      onSuccess: (me) => {
        queryClient.setQueryData(["me"], me);
        onConfirmed();
      },
    });
  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={t("security.reauth.title")}
      description={t("security.reauth.desc")}
      footer={
        account.has_password && (
          <>
            <DialogClose asChild>
              <Button>{t("security.cancel")}</Button>
            </DialogClose>
            <Button type="submit" form={formId} variant="ink" disabled={!password || reauthenticate.isPending}>
              {t("security.reauth.submit")}
            </Button>
          </>
        )
      }
    >
      {account.has_password && (
        <form
          id={formId}
          className="m-0"
          onSubmit={(event) => {
            event.preventDefault();
            reauthenticate.mutate(password, { onSuccess: onConfirmed });
          }}
        >
          <PasswordField
            label={t("auth.password")}
            autoComplete="current-password"
            autoFocus
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
              if (reauthenticate.isError) reauthenticate.reset();
            }}
            error={
              reauthenticate.isError
                ? errorText(reauthenticate.error, { invalid_credentials: t("security.reauth.wrong") })
                : undefined
            }
          />
        </form>
      )}
      {account.has_passkey && (
        <ProviderButton onClick={withPasskey} disabled={passkey.isPending} logo={<PasskeyLogo />}>
          {passkey.isPending ? t("security.waiting") : t("security.reauth.passkey")}
        </ProviderButton>
      )}
      {!account.has_password && !account.has_passkey && (
        <ProviderButton href={`/v1/auth/google/start?next=${encodeURIComponent(window.location.pathname)}`} logo={<GoogleLogo />}>
          {t("auth.google")}
        </ProviderButton>
      )}
      {passkeyError(passkey.error) && (
        <p role="alert" className="m-0 text-12 text-err">
          {passkeyError(passkey.error)}
        </p>
      )}
    </Dialog>
  );
}
