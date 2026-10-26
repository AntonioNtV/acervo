import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { useErrorText } from "../../app/errors";
import { useResubscribe, useUnsubscribe } from "../../data/account";
import { ApiError } from "../../data/request";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { AuthCard, AuthError, authLink } from "./AuthCard";

/** The toggle the link carries, read from the token's signed body; the server has already checked it when shown. */
function toggleOf(token: string): "invites" | "followed" {
  try {
    const body = token.slice(0, token.lastIndexOf(".")).replaceAll("-", "+").replaceAll("_", "/");
    return JSON.parse(atob(body)).notification === "followed" ? "followed" : "invites";
  } catch {
    return "invites";
  }
}

/** `/descadastro/:token`, the "Parar de receber" link of an email: turns that toggle off on opening, without signing in. */
export function Unsubscribe() {
  const { t } = useI18n();
  const errorText = useErrorText();
  const { token = "" } = useParams();
  const unsubscribe = useUnsubscribe();
  const resubscribe = useResubscribe();
  const { mutate } = unsubscribe;
  useEffect(() => mutate(token), [mutate, token]);

  const toggle = t(`notifications.${toggleOf(token)}`);
  const foot = (
    <>
      {t("unsubscribe.choose")}{" "}
      <Link to="/conta/notificacoes" className={authLink}>
        {t("notifications.title")}
      </Link>
      .
    </>
  );

  if (unsubscribe.error instanceof ApiError && unsubscribe.error.code === "not_found")
    return (
      <AuthCard title={t("unsubscribe.invalid")} desc={t("unsubscribe.invalid.desc")}>
        <Link
          to="/entrar"
          className="inline-flex h-[30px] w-full items-center justify-center rounded-[7px] border border-ink bg-ink text-13 font-medium text-on-ink no-underline"
        >
          {t("unsubscribe.signIn")}
        </Link>
      </AuthCard>
    );
  if (unsubscribe.isError)
    return (
      <AuthCard title={t("unsubscribe.off.title")}>
        <AuthError>{errorText(unsubscribe.error)}</AuthError>
      </AuthCard>
    );
  if (!unsubscribe.isSuccess) return null;
  if (resubscribe.isSuccess)
    return <AuthCard title={t("unsubscribe.on.title")} desc={t("unsubscribe.on.desc", { toggle })} foot={foot} />;
  return (
    <AuthCard title={t("unsubscribe.off.title")} desc={t("unsubscribe.off.desc", { toggle })} foot={foot}>
      <Button className="w-full" disabled={resubscribe.isPending} onClick={() => resubscribe.mutate(token)}>
        {t("unsubscribe.undo")}
      </Button>
      {resubscribe.isError && <AuthError>{errorText(resubscribe.error)}</AuthError>}
    </AuthCard>
  );
}
