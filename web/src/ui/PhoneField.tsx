import { useId } from "react";
import { useI18n } from "../i18n";
import { Input } from "./Input";
import { SelectField } from "./SelectField";

// shortcut: a few countries by their calling code, add more when someone outside them asks.
const COUNTRIES = [
  { value: "55", label: "BR +55" },
  { value: "351", label: "PT +351" },
  { value: "1", label: "US +1" },
  { value: "54", label: "AR +54" },
];

/** `(11) 98765-4821` while a Brazilian number is typed; other countries keep the digits as typed. */
function shown(country: string, digits: string) {
  if (country !== "55" || digits.length < 3) return digits;
  const local = digits.slice(2);
  const split = local.length > 8 ? 5 : 4;
  return `(${digits.slice(0, 2)}) ${local.slice(0, split)}${local.length > split ? `-${local.slice(split)}` : ""}`;
}

/** The number in E.164 (`+5511987654821`), or null while it cannot be a number of that country. */
export function e164({ country, digits }: Phone): string | null {
  const ok = country === "55" ? digits.length === 10 || digits.length === 11 : digits.length >= 6 && digits.length <= 14;
  return ok ? `+${country}${digits}` : null;
}

export type Phone = { country: string; digits: string };

/** The WhatsApp number of two-step verification: the country's code, Brasil by default, and the number. */
export function PhoneField({ value, onChange, error }: { value: Phone; onChange: (value: Phone) => void; error?: string }) {
  const { t } = useI18n();
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5 text-12 text-text-2">
      <label htmlFor={id}>{t("security.phone")}</label>
      <span className="flex gap-1.5">
        <SelectField
          label={t("security.phone.country")}
          width={96}
          value={value.country}
          options={COUNTRIES}
          onChange={(country) => onChange({ ...value, country })}
        />
        <Input
          id={id}
          type="tel"
          inputMode="tel"
          autoComplete="tel-national"
          autoFocus
          value={shown(value.country, value.digits)}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          onChange={(event) => onChange({ ...value, digits: event.target.value.replace(/\D/g, "").slice(0, 14) })}
        />
      </span>
      {error && (
        <span id={`${id}-error`} role="alert" className="-mt-0.5 text-err">
          {error}
        </span>
      )}
    </div>
  );
}
