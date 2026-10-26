import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useErrorText } from "../../app/errors";
import { useConfirmReset, useRequestReset } from "../../data/account";
import { ApiError } from "../../data/request";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { PasswordField } from "../../ui/PasswordField";
import { AuthCard, AuthError, AuthField, authLink } from "./AuthCard";

function BackToSignIn() {
  const { t } = useI18n();
  return (
    <Link to="/entrar" className={authLink}>
      {t("auth.back")}
    </Link>
  );
}

/** `/redefinir-senha`: asks for the link; the answer never says whether the email has an account. */
export function ResetRequest() {
  const { t } = useI18n();
  const errorText = useErrorText();
  const [email, setEmail] = useState("");
  const reset = useRequestReset();

  if (reset.isSuccess)
    return (
      <AuthCard title={t("auth.sent.title")} desc={t("auth.sent.desc", { email: reset.variables })} foot={<BackToSignIn />} />
    );
  return (
    <AuthCard
      title={t("auth.reset.title")}
      desc={t("auth.reset.desc")}
      onSubmit={() => reset.mutate(email.trim())}
      foot={<BackToSignIn />}
    >
      <AuthField
        label={t("auth.email")}
        type="email"
        autoComplete="email"
        required
        autoFocus
        placeholder={t("auth.email.placeholder")}
        value={email}
        onChange={(event) => setEmail(event.target.value)}
      />
      {reset.isError && <AuthError>{errorText(reset.error)}</AuthError>}
      <Button type="submit" variant="ink" className="w-full" disabled={reset.isPending}>
        {t("auth.reset.submit")}
      </Button>
    </AuthCard>
  );
}

/** `/redefinir-senha/:token`, from the email: the new password starts a session and ends every other one. */
export function NewPassword() {
  const { t } = useI18n();
  const errorText = useErrorText();
  const navigate = useNavigate();
  const { token = "" } = useParams();
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [mismatch, setMismatch] = useState(false);
  const confirm = useConfirmReset();

  if (confirm.error instanceof ApiError && confirm.error.code === "code_invalid")
    return (
      <AuthCard title={t("auth.expired.title")} desc={t("auth.expired.desc")} foot={<BackToSignIn />}>
        <Link
          to="/redefinir-senha"
          className="inline-flex h-[30px] w-full items-center justify-center rounded-[7px] border border-ink bg-ink text-13 font-medium text-on-ink no-underline"
        >
          {t("auth.expired.again")}
        </Link>
      </AuthCard>
    );

  function submit() {
    setMismatch(password !== repeat);
    if (password === repeat) confirm.mutate({ token, password }, { onSuccess: () => navigate("/bases", { replace: true }) });
  }

  return (
    <AuthCard title={t("auth.newPassword.title")} desc={t("auth.newPassword.desc")} onSubmit={submit}>
      <PasswordField
        label={t("auth.newPassword.title")}
        autoComplete="new-password"
        required
        minLength={10}
        autoFocus
        hint={t("auth.password.hint")}
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      <PasswordField
        label={t("auth.newPassword.repeat")}
        autoComplete="new-password"
        required
        value={repeat}
        onChange={(event) => setRepeat(event.target.value)}
        error={mismatch ? t("auth.newPassword.mismatch") : undefined}
      />
      {confirm.isError && <AuthError>{errorText(confirm.error)}</AuthError>}
      <Button type="submit" variant="ink" className="w-full" disabled={confirm.isPending}>
        {t("auth.newPassword.submit")}
      </Button>
    </AuthCard>
  );
}
