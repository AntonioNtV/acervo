import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useErrorText } from "../../app/errors";
import { useLinkGoogle } from "../../data/account";
import { ApiError } from "../../data/request";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { PasswordField } from "../../ui/PasswordField";
import { AuthCard, AuthError, authLink, useNext } from "./AuthCard";

/**
 * `/entrar/vincular?token=…`: Google confirmed an email whose account was not confirmed on both sides, so that
 * account's password is asked once before the two are linked.
 */
export function LinkGoogle() {
  const { t } = useI18n();
  const errorText = useErrorText();
  const navigate = useNavigate();
  const next = useNext();
  const [params] = useSearchParams();
  const [password, setPassword] = useState("");
  const link = useLinkGoogle();
  const code = link.error instanceof ApiError ? link.error.code : "";
  const back = (
    <Link to={`/entrar?next=${encodeURIComponent(next)}`} className={authLink}>
      {t("auth.back")}
    </Link>
  );

  if (code === "code_invalid") return <AuthCard title={t("auth.link.title")} desc={t("auth.link.expired")} foot={back} />;
  return (
    <AuthCard
      title={t("auth.link.title")}
      desc={t("auth.link.desc")}
      foot={back}
      onSubmit={() =>
        link.mutate(
          { token: params.get("token") ?? "", password },
          { onSuccess: () => navigate(next, { replace: true }) },
        )
      }
    >
      <PasswordField
        label={t("auth.password")}
        autoComplete="current-password"
        required
        autoFocus
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        error={code === "invalid_credentials" ? t("auth.link.wrong") : undefined}
      />
      {link.isError && code !== "invalid_credentials" && <AuthError>{errorText(link.error)}</AuthError>}
      <Button type="submit" variant="ink" className="w-full" disabled={link.isPending}>
        {t("auth.link.submit")}
      </Button>
    </AuthCard>
  );
}
