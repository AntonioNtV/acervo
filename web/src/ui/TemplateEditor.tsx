import { useId } from "react";
import { useI18n } from "../i18n";
import { Input } from "./Input";

/** What a Button block holds: its label and the blocks it inserts, as a panel the caller places. Escape closes it. */
export function TemplateEditor({
  label,
  lines,
  onChange,
  onClose,
}: {
  label: string;
  /** The template's blocks, one per line, as they enter the page. */
  lines: string[];
  onChange: (label: string) => void;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const id = useId();
  const invalid = !label.trim();
  return (
    <div
      role="dialog"
      aria-label={t("pickers.template.label")}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.stopPropagation();
          onClose();
        }
      }}
      className="flex w-[300px] max-w-full flex-col gap-2 rounded-[8px] border border-line-2 bg-bg p-3 text-13 text-text"
    >
      <label htmlFor={id} className="text-12 text-text-2">
        {t("pickers.template.field")}
      </label>
      <Input
        id={id}
        autoFocus
        value={label}
        placeholder={t("pickers.template.placeholder")}
        aria-invalid={invalid}
        onChange={(event) => onChange(event.target.value)}
      />
      {invalid && (
        <span role="alert" className="text-12 text-err">
          {t("pickers.template.invalid")}
        </span>
      )}
      <span className="text-12 text-text-2">{t("pickers.template.caption")}</span>
      <div className="rounded-[6px] border border-line px-2.5 py-2 text-13 leading-[22px] text-text-2">
        {lines.map((line, i) => (
          <div key={i}>{line}</div>
        ))}
      </div>
    </div>
  );
}
