import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useErrorText } from "../../app/errors";
import { useForgetAccount } from "../../app/lastPage";
import { useSignIn } from "../../data/account";
import { isPending, passkeySignIn, usePasskeySignIn } from "../../data/security";
import { ApiError } from "../../data/request";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { PasswordField } from "../../ui/PasswordField";
import { PasskeyLogo, ProviderButton } from "../../ui/ProviderButton";
import { autofillAvailable, cancelled } from "../../webauthn";
import { usePasskeyError } from "../settings/ReauthDialog";
import { AuthCard, AuthError, AuthField, authLink, GoogleFirst, useNext } from "./AuthCard";

/**
 * `/entrar`: Google, a passkey (its button, or the browser's autofill on the email field), or email and password; a
 * wrong one of the two is never told apart. With two-step verification on, the password leads to the code.
 */
export function SignIn() {
  const { t } = useI18n();
  const errorText = useErrorText();
  const navigate = useNavigate();
  const forget = useForgetAccount();
  const next = useNext();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const signIn = useSignIn();
  const passkey = usePasskeySignIn();
  const passkeyError = usePasskeyError();
  const [autofillError, setAutofillError] = useState<unknown>(null);
  const autofill = useRef<AbortController | null>(null);
  const code = signIn.error instanceof ApiError ? signIn.error.code : "";
  const locked = code === "too_many_attempts";
  const failedPasskey = passkeyError(passkey.error ?? autofillError);

  function signedIn() {
    forget();
    navigate(next, { replace: true });
  }
  // Read by the autofill, which starts once and outlives renders.
  const signedInRef = useRef(signedIn);
  signedInRef.current = signedIn;

  useEffect(() => {
    const controller = new AbortController();
    autofill.current = controller;
    (async () => {
      if (!(await autofillAvailable())) return;
      await passkeySignIn(controller.signal);
      signedInRef.current();
    })().catch((error: unknown) => {
      if (!cancelled(error)) setAutofillError(error);
    });
    return () => controller.abort();
  }, []);

  function withPasskey() {
    // The browser runs one prompt at a time: the autofill's gives way to the button's.
    autofill.current?.abort();
    setAutofillError(null);
    passkey.mutate(undefined, { onSuccess: signedIn });
  }

  function submit() {
    signIn.mutate(
      { email: email.trim(), password },
      {
        onSuccess: (answer) => {
          if (isPending(answer)) navigate(`/entrar/codigo?next=${encodeURIComponent(next)}`, { state: answer });
          else signedIn();
        },
        onError: (error) => {
          // The API sent a new code: the account only needs its email confirmed.
          if (error instanceof ApiError && error.code === "email_not_verified")
            navigate(`/confirmar-email?next=${encodeURIComponent(next)}`, { state: { email: email.trim() } });
        },
      },
    );
  }

  const createLink = (
    <Link to={`/criar-conta?next=${encodeURIComponent(next)}`} className={authLink}>
      {t("auth.signIn.create")}
    </Link>
  );
  return (
    <AuthCard
      title={t("auth.signIn.title")}
      onSubmit={submit}
      foot={
        <>
          {t("auth.signIn.noAccount")} {createLink}
        </>
      }
    >
      {!locked && (
        <GoogleFirst next={next}>
          <ProviderButton onClick={withPasskey} disabled={passkey.isPending} logo={<PasskeyLogo />}>
            {passkey.isPending ? t("security.waiting") : t("security.passkey.signIn")}
          </ProviderButton>
          {failedPasskey && <AuthError>{failedPasskey}</AuthError>}
        </GoogleFirst>
      )}
      {params.get("erro") === "google" && !signIn.isError && <AuthError>{t("auth.google.failed")}</AuthError>}
      <AuthField
        label={t("auth.email")}
        type="email"
        autoComplete="username webauthn"
        required
        autoFocus
        placeholder={t("auth.email.placeholder")}
        value={email}
        onChange={(event) => {
          setEmail(event.target.value);
          if (locked) signIn.reset();
        }}
      />
      {locked ? (
        <AuthError>
          {t("auth.signIn.locked")}{" "}
          <Link to="/redefinir-senha" className={authLink}>
            {t("auth.signIn.locked.reset")}
          </Link>
          .
        </AuthError>
      ) : (
        <PasswordField
          label={t("auth.password")}
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          error={code === "invalid_credentials" ? errorText(signIn.error) : undefined}
          aside={
            <Link to="/redefinir-senha" className="text-text-3 no-underline hover:text-text">
              {t("auth.signIn.forgot")}
            </Link>
          }
        />
      )}
      {signIn.isError && !locked && code !== "invalid_credentials" && code !== "email_not_verified" && (
        <AuthError>{errorText(signIn.error)}</AuthError>
      )}
      <Button type="submit" variant="ink" className="w-full" disabled={locked || signIn.isPending}>
        {t("auth.signIn.submit")}
      </Button>
    </AuthCard>
  );
}
