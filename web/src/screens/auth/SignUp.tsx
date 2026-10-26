import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useErrorText } from "../../app/errors";
import { useSignUp } from "../../data/account";
import { ApiError } from "../../data/request";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { PasswordField } from "../../ui/PasswordField";
import { AuthCard, AuthError, AuthField, authLink, GoogleFirst, useNext } from "./AuthCard";

/** `/criar-conta`: Google, or name, email and password, then the code sent to the email. */
export function SignUp() {
  const { t } = useI18n();
  const errorText = useErrorText();
  const navigate = useNavigate();
  const next = useNext();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const signUp = useSignUp();
  const taken = signUp.error instanceof ApiError && signUp.error.code === "email_taken";
  const signInLink = (
    <Link to={`/entrar?next=${encodeURIComponent(next)}`} className={authLink}>
      {t("auth.signUp.signIn")}
    </Link>
  );

  function submit() {
    const body = { name: name.trim(), email: email.trim(), password };
    signUp.mutate(body, {
      onSuccess: () => navigate(`/confirmar-email?next=${encodeURIComponent(next)}`, { state: { email: body.email } }),
    });
  }

  return (
    <AuthCard
      title={t("auth.signUp.title")}
      onSubmit={submit}
      foot={
        <>
          {t("auth.signUp.hasAccount")} {signInLink}
        </>
      }
    >
      <GoogleFirst next={next} />
      <AuthField
        label={t("auth.name")}
        autoComplete="name"
        required
        autoFocus
        placeholder={t("auth.name.placeholder")}
        value={name}
        onChange={(event) => setName(event.target.value)}
      />
      <AuthField
        label={t("auth.email")}
        type="email"
        autoComplete="email"
        required
        placeholder={t("auth.email.placeholder")}
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        error={
          taken && (
            <>
              {errorText(signUp.error)} {signInLink}
            </>
          )
        }
      />
      <PasswordField
        label={t("auth.password")}
        autoComplete="new-password"
        required
        minLength={10}
        hint={t("auth.password.hint")}
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      {signUp.isError && !taken && <AuthError>{errorText(signUp.error)}</AuthError>}
      <Button type="submit" variant="ink" className="w-full" disabled={signUp.isPending}>
        {t("auth.signUp.submit")}
      </Button>
    </AuthCard>
  );
}
