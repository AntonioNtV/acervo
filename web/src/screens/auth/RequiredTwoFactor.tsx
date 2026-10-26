import { useState } from "react";
import { useErrorText } from "../../app/errors";
import { useAddPasskey, useStartTwoFactor } from "../../data/security";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { MethodGlyph, type MethodIcon } from "../../ui/SecurityMethodRow";
import { usePasskeyError } from "../settings/ReauthDialog";
import { WhatsAppForm } from "../settings/Security";
import { AuthCard, AuthError, authLink } from "./AuthCard";

type Method = "passkey" | "whatsapp" | "email";
const METHODS: [Method, MethodIcon][] = [
  ["passkey", "passkey"],
  ["whatsapp", "chat"],
  ["email", "mail"],
];

/**
 * "2FA exigido": an organization requires a passkey or two-step verification the account does not have. Its bases
 * stay closed until one is on; the Pessoal and the other organizations stay open through `onLeave`.
 */
export function RequiredTwoFactor({
  organization,
  onDone,
  onLeave,
}: {
  organization: string;
  onDone: () => void;
  onLeave: () => void;
}) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const passkeyError = usePasskeyError();
  const add = useAddPasskey();
  const start = useStartTwoFactor();
  const [method, setMethod] = useState<Method>("passkey");
  const [step, setStep] = useState<"method" | "phone" | "code">("method");
  const failed = passkeyError(add.error) ?? (start.isError ? errorText(start.error) : undefined);

  if (step !== "method")
    return (
      <AuthCard
        title={t(step === "phone" ? "security.whatsapp.title" : "security.whatsapp.confirm")}
        desc={step === "phone" ? t("security.whatsapp.desc") : undefined}
        foot={
          step === "phone" && (
            <button type="button" className={`cursor-pointer border-0 bg-transparent p-0 text-13 ${authLink}`} onClick={() => setStep("method")}>
              {t("security.back")}
            </button>
          )
        }
      >
        <WhatsAppForm onDone={onDone} onSent={(sent) => setStep(sent ? "code" : "phone")} />
      </AuthCard>
    );

  return (
    <AuthCard
      title={t("security.required.title")}
      desc={t("security.required.desc", { organization })}
      onSubmit={() => {
        if (method === "passkey") add.mutate(undefined, { onSuccess: onDone });
        else if (method === "email") start.mutate({ method: "email" }, { onSuccess: onDone });
        else setStep("phone");
      }}
      foot={
        <button type="button" className={`cursor-pointer border-0 bg-transparent p-0 text-13 ${authLink}`} onClick={onLeave}>
          {t("security.required.leave")}
        </button>
      }
    >
      <div role="radiogroup" aria-label={t("security.required.title")} className="flex flex-col border-t border-line">
        {METHODS.map(([value, icon]) => (
          <label key={value} className="flex cursor-pointer items-center gap-3 border-b border-line py-2.5">
            <input
              type="radio"
              name="method"
              className="m-0 accent-ink"
              checked={method === value}
              onChange={() => {
                setMethod(value);
                add.reset();
                start.reset();
              }}
            />
            <span className="inline-flex text-text-3">
              <MethodGlyph icon={icon} />
            </span>
            <span className="flex flex-col">
              <span className="text-13 text-text">{t(`security.required.${value}`)}</span>
              <span className="text-12 leading-[18px] text-text-3">{t(`security.required.${value}.desc`)}</span>
            </span>
          </label>
        ))}
      </div>
      {failed && <AuthError>{failed}</AuthError>}
      <Button type="submit" variant="ink" className="w-full" disabled={add.isPending || start.isPending}>
        {add.isPending ? t("security.waiting") : t("security.required.continue")}
      </Button>
    </AuthCard>
  );
}
