import { useEffect, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useErrorText } from "../../app/errors";
import { useForgetAccount } from "../../app/lastPage";
import { useFinishTwoFactor, useResendTwoFactor, type PendingSignIn } from "../../data/security";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { CodeInput } from "../../ui/CodeInput";
import { AuthCard, AuthError, authLink, useNext } from "./AuthCard";

const RESEND_AFTER_S = 60;

/** `a••••@segura.com.br`: enough to recognize the address on a shared screen. */
export function mask(email: string) {
  const at = email.indexOf("@");
  return at < 1 ? email : `${email[0]}••••${email.slice(at)}`;
}

/**
 * `/entrar/codigo`: the code of a password sign-in with two-step verification on. Entrar left the pending sign-in in
 * the router's state; the right code starts the session.
 */
export function TwoFactor() {
  const { t } = useI18n();
  const errorText = useErrorText();
  const navigate = useNavigate();
  const forget = useForgetAccount();
  const next = useNext();
  const [pending, setPending] = useState(useLocation().state as PendingSignIn | null);
  const [code, setCode] = useState("");
  const [sentAt, setSentAt] = useState(Date.now);
  const [now, setNow] = useState(Date.now);
  const finish = useFinishTwoFactor();
  const resend = useResendTwoFactor();
  const wait = Math.max(0, RESEND_AFTER_S - Math.floor((now - sentAt) / 1000));

  useEffect(() => {
    if (wait === 0) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [wait]);

  if (!pending?.pending) return <Navigate replace to={`/entrar?next=${encodeURIComponent(next)}`} />;

  const again = (channel?: "email") =>
    resend.mutate(channel, {
      onSuccess: (sent) => {
        const at = Date.now();
        setPending(sent);
        setSentAt(at);
        setNow(at);
        setCode("");
        finish.reset();
      },
    });

  return (
    <AuthCard
      title={t("security.code.title")}
      desc={t("security.code.desc")}
      foot={
        <Link to={`/entrar?next=${encodeURIComponent(next)}`} className={authLink}>
          {t("auth.back")}
        </Link>
      }
    >
      <CodeInput
        value={code}
        onChange={(value) => {
          setCode(value);
          if (finish.isError) finish.reset();
        }}
        onComplete={(value) =>
          finish.mutate(value, {
            onSuccess: () => {
              forget();
              navigate(next, { replace: true });
            },
          })
        }
        sent={t(pending.method === "whatsapp" ? "security.code.sent.whatsapp" : "auth.verify.sent", {
          email: pending.destination,
          number: pending.destination,
        })}
        checking={finish.isPending}
        error={finish.isError ? errorText(finish.error) : undefined}
        footer={
          <>
            {wait > 0 ? (
              t("auth.verify.wait", { time: `${Math.floor(wait / 60)}:${String(wait % 60).padStart(2, "0")}` })
            ) : (
              <Button variant="quiet" size="sm" className="-ml-2 font-normal" disabled={resend.isPending} onClick={() => again()}>
                {t("auth.verify.resend")}
              </Button>
            )}
            {pending.method === "whatsapp" && (
              <Button variant="quiet" size="sm" className="-mr-2 font-normal" disabled={resend.isPending} onClick={() => again("email")}>
                {t("security.code.byEmail")}
              </Button>
            )}
          </>
        }
      />
      {resend.isError && <AuthError>{errorText(resend.error, { too_many_attempts: t("security.code.wait") })}</AuthError>}
    </AuthCard>
  );
}
