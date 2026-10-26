import { useId, useState, type InputHTMLAttributes, type ReactNode } from "react";
import { useI18n } from "../i18n";
import { IconButton } from "./IconButton";
import { Input } from "./Input";

// Glyphs only this field uses, so they stay out of Icon's set.
const EYE = (
  <>
    <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" />
    <circle cx="12" cy="12" r="3" />
  </>
);
const EYE_OFF = (
  <path d="M4 4l16 16M10.6 6.1A9 9 0 0 1 12 6c6 0 9.5 6 9.5 6a16 16 0 0 1-2.6 3.3M6.6 7.6C4 9.2 2.5 12 2.5 12S6 18 12 18c1.6 0 3-.4 4.2-1" />
);

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  label: string;
  /** The rule under the field, replaced by `error` when there is one. */
  hint?: string;
  error?: string;
  /** At the right of the label, such as "Esqueci a senha". */
  aside?: ReactNode;
};

/** A password input with Mostrar/Ocultar inside it and its rule or error below. */
export function PasswordField({ label, hint, error, aside, ...rest }: Props) {
  const { t } = useI18n();
  const id = useId();
  const [visible, setVisible] = useState(false);
  const below = error ?? hint;
  return (
    <div className="flex flex-col gap-1.5 text-12 text-text-2">
      <span className="flex justify-between">
        <label htmlFor={id}>{label}</label>
        {aside}
      </span>
      <span className="relative flex items-center">
        <Input
          id={id}
          type={visible ? "text" : "password"}
          className="pr-[34px]"
          aria-invalid={error ? true : undefined}
          aria-describedby={below ? `${id}-below` : undefined}
          {...rest}
        />
        <IconButton
          size="sm"
          className="absolute right-1"
          aria-label={t(visible ? "auth.password.hide" : "auth.password.show")}
          aria-pressed={visible}
          onClick={() => setVisible(!visible)}
        >
          <svg
            viewBox="0 0 24 24"
            width={14}
            height={14}
            aria-hidden="true"
            className="fill-none stroke-current stroke-[1.5]"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            {visible ? EYE_OFF : EYE}
          </svg>
        </IconButton>
      </span>
      {below && (
        <span id={`${id}-below`} role={error ? "alert" : undefined} className={error ? "-mt-0.5 text-err" : "-mt-0.5 text-text-3"}>
          {below}
        </span>
      )}
    </div>
  );
}
