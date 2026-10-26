import { useI18n } from "../i18n";

/** Turns a value on or off, with Sim/Não written beside it; on is ink. */
export function SwitchControl({
  label,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  return (
    <span className="inline-flex items-center gap-2 text-13 text-text">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className="relative h-[18px] w-8 shrink-0 cursor-pointer rounded-[9px] border-0 bg-line-2 p-0 after:absolute after:top-0.5 after:left-0.5 after:size-3.5 after:rounded-full after:bg-bg after:transition-transform after:duration-[120ms] aria-checked:bg-ink aria-checked:after:translate-x-3.5 disabled:cursor-default disabled:opacity-50"
      />
      <span>{checked ? t("controls.yes") : t("controls.no")}</span>
    </span>
  );
}
