import type { ReactNode } from "react";

/** A native checkbox in ink with its label, which a click also toggles. */
export function CheckboxControl({
  checked,
  onChange,
  disabled,
  children,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-13 text-text has-disabled:cursor-default">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="m-0 size-[15px] cursor-pointer accent-ink disabled:cursor-default"
      />
      {children}
    </label>
  );
}
