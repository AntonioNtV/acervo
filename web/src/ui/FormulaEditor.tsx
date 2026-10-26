import { useI18n } from "../i18n";
import { cx } from "./cx";

/** Enough to read the formula while typing, not a TeX renderer. */
function preview(source: string): string {
  return source
    .replace(/\\times/g, "×")
    .replace(/\\cdot/g, "·")
    .replace(/\\leq/g, "≤")
    .replace(/\\geq/g, "≥")
    .replace(/[{}\\]/g, "");
}

/**
 * The source of an equation (`tex`, with a serif preview) or of a value formula (`sheet`), as a panel the caller
 * places. Enter closes it, keeping the source, unless there is an error; Escape cancels.
 */
export function FormulaEditor({
  kind,
  source,
  error,
  onChange,
  onClose,
  onCancel,
}: {
  kind: "tex" | "sheet";
  source: string;
  /** What is wrong with the source, in words. */
  error?: string;
  onChange: (source: string) => void;
  onClose: () => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  return (
    <div
      role="dialog"
      aria-label={t("pickers.formula.label")}
      className="flex w-[360px] max-w-full flex-col gap-1.5 rounded-[8px] border border-line-2 bg-bg px-2.5 py-2 text-13 text-text"
    >
      <label
        className={cx(
          "flex rounded-[7px] border px-2.5 py-1.5 font-mono text-12",
          error ? "border-err" : "border-line-2 focus-within:border-ink",
        )}
      >
        {kind === "sheet" && <span className="pr-1">=</span>}
        <input
          autoFocus
          aria-label={t("pickers.formula.source")}
          aria-invalid={!!error}
          value={source}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              if (!error) onClose();
            } else if (event.key === "Escape") {
              event.stopPropagation();
              onCancel();
            }
          }}
          className="min-w-0 flex-1 border-0 bg-transparent p-0 font-mono text-12 text-text outline-none focus-visible:outline-none"
        />
      </label>
      {kind === "tex" && !error && (
        <div className="text-center font-serif text-[17px] leading-[26px] italic">{preview(source)}</div>
      )}
      {error ? (
        <span role="alert" className="text-12 text-err">
          {error}
        </span>
      ) : (
        <span className="text-12 text-text-3">{t("pickers.formula.hint")}</span>
      )}
    </div>
  );
}
