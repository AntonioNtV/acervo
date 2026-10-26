import { useState, type ReactNode } from "react";
import { useI18n } from "../i18n";
import { cx } from "./cx";

type Props = {
  value: string;
  onChange: (code: string) => void;
  /** Called with the code once the sixth digit is typed or pasted: there is no Confirmar button. */
  onComplete: (code: string) => void;
  /** Where the code went, above the cells. */
  sent: string;
  error?: string;
  checking?: boolean;
  /** Under the cells: the countdown or the Reenviar link. */
  footer?: ReactNode;
};

/** A 6-digit code: one input under six drawn cells, so pasting fills them all and the browser can offer the code. */
export function CodeInput({ value, onChange, onComplete, sent, error, checking = false, footer }: Props) {
  const { t } = useI18n();
  const [focused, setFocused] = useState(false);
  return (
    <div className="flex flex-col gap-3">
      <span className="text-13 text-text-3">{sent}</span>
      <div className={cx("relative flex items-center gap-2", checking && "opacity-50")}>
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <span key={i} className="contents">
            {i === 3 && <span aria-hidden="true" className="h-px w-2 bg-ghost" />}
            <span
              aria-hidden="true"
              className={cx(
                "inline-flex h-12 w-10 items-center justify-center rounded-[7px] border bg-bg font-mono text-20 font-medium text-text",
                error ? "border-err" : "border-line-2",
                focused && i === Math.min(value.length, 5) && !error && "border-ink shadow-[0_0_0_3px_var(--accent-soft)]",
              )}
            >
              {value[i]}
            </span>
          </span>
        ))}
        <input
          aria-label={t("auth.code.label")}
          autoComplete="one-time-code"
          inputMode="numeric"
          autoFocus
          disabled={checking}
          value={value}
          aria-invalid={error ? true : undefined}
          className="absolute inset-0 cursor-default opacity-0"
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onChange={(event) => {
            const code = event.target.value.replace(/\D/g, "").slice(0, 6);
            onChange(code);
            if (code.length === 6) onComplete(code);
          }}
        />
      </div>
      {error && (
        <span role="alert" className="-mt-1 text-12 text-err">
          {error}
        </span>
      )}
      {footer && <span className="flex items-center justify-between text-12 text-ghost">{footer}</span>}
    </div>
  );
}
