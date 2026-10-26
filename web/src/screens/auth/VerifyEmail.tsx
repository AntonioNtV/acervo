import { useEffect, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useErrorText } from "../../app/errors";
import { useResendCode, useVerifyEmail } from "../../data/account";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { CodeInput } from "../../ui/CodeInput";
import { AuthCard, AuthError, authLink, useNext } from "./AuthCard";

const RESEND_AFTER_S = 60;

/** `a••••@segura.com.br`: enough to recognize the address on a shared screen. */
function mask(email: string) {
  const at = email.indexOf("@");
  return at < 1 ? email : `${email[0]}••••${email.slice(at)}`;
}

/**
 * `/confirmar-email`: the code just sent to the email the previous screen held in the router's state, so the address
 * never goes in the URL. The right code starts the session.
 */
export function VerifyEmail() {
  const { t } = useI18n();
  const errorText = useErrorText();
  const navigate = useNavigate();
  const next = useNext();
  const email = (useLocation().state as { email?: string } | null)?.email;
  const [code, setCode] = useState("");
  const [sentAt, setSentAt] = useState(Date.now);
  const [now, setNow] = useState(Date.now);
  const verify = useVerifyEmail();
  const resend = useResendCode();
  const wait = Math.max(0, RESEND_AFTER_S - Math.floor((now - sentAt) / 1000));

  useEffect(() => {
    if (wait === 0) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [wait]);

  if (!email) return <Navigate replace to="/entrar" />;

  function again() {
    resend.mutate(email!, {
      onSuccess: () => {
        const at = Date.now();
        setSentAt(at);
        setNow(at);
        setCode("");
        verify.reset();
      },
    });
  }

  return (
    <AuthCard
      title={t("auth.verify.title")}
      desc={t("auth.verify.desc")}
      foot={
        <>
          {t("auth.verify.wrongEmail")}{" "}
          <Link to={`/criar-conta?next=${encodeURIComponent(next)}`} className={authLink}>
            {t("auth.verify.changeEmail")}
          </Link>
        </>
      }
    >
      <CodeInput
        value={code}
        onChange={(value) => {
          setCode(value);
          if (verify.isError) verify.reset();
        }}
        onComplete={(value) => verify.mutate({ email, code: value }, { onSuccess: () => navigate(next, { replace: true }) })}
        sent={t("auth.verify.sent", { email: mask(email) })}
        checking={verify.isPending}
        error={verify.isError ? errorText(verify.error) : undefined}
        footer={
          wait > 0 ? (
            t("auth.verify.wait", { time: `${Math.floor(wait / 60)}:${String(wait % 60).padStart(2, "0")}` })
          ) : (
            <Button variant="quiet" size="sm" className="-ml-2 font-normal" disabled={resend.isPending} onClick={again}>
              {t("auth.verify.resend")}
            </Button>
          )
        }
      />
      {resend.isError && <AuthError>{errorText(resend.error)}</AuthError>}
    </AuthCard>
  );
}
