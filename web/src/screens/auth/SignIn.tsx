import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useErrorText } from "../../app/errors";
import { useForgetAccount } from "../../app/lastPage";
import { useSignIn } from "../../data/account";
import { ApiError } from "../../data/request";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { PasswordField } from "../../ui/PasswordField";
import { AuthCard, AuthError, AuthField, authLink, GoogleFirst, useNext } from "./AuthCard";

/** `/entrar`: Google, or email and password; a wrong one of the two is never told apart. */
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
  const code = signIn.error instanceof ApiError ? signIn.error.code : "";
  const locked = code === "too_many_attempts";

  function submit() {
    signIn.mutate(
      { email: email.trim(), password },
      {
        onSuccess: () => {
          forget();
          navigate(next, { replace: true });
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
      {!locked && <GoogleFirst next={next} />}
      {params.get("erro") === "google" && !signIn.isError && <AuthError>{t("auth.google.failed")}</AuthError>}
      <AuthField
        label={t("auth.email")}
        type="email"
        autoComplete="email"
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
