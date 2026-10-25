import { cx } from "./cx";

type Option<T extends string> = { value: T; label: string };

type Props<T extends string> = {
  label: string;
  options: Option<T>[];
  value: T;
  onChange: (value: T) => void;
  size?: "md" | "lg";
  disabled?: boolean;
};

export function TextTabs<T extends string>({ label, options, value, onChange, size = "md", disabled }: Props<T>) {
  return (
    <div role="group" aria-label={label} className={cx("flex", size === "lg" ? "gap-5" : "gap-4")}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={option.value === value}
          disabled={disabled}
          onClick={() => onChange(option.value)}
          className={cx(
            "cursor-pointer border-0 bg-transparent p-0 text-text-3 aria-pressed:text-text enabled:hover:text-text",
            "disabled:cursor-default",
            size === "lg" ? "text-15 tracking-[-0.01em]" : "text-13",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
