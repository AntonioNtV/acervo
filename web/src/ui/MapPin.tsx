import { cx } from "./cx";
import type { Tone } from "./Dot";
import { StatusValue } from "./StatusValue";

/** A row of a database on the map: an ink pin and, while selected, its popover. Escape or a second click closes it. */
export function MapPin({
  label,
  selected,
  title,
  meta,
  status,
  value,
  onSelect,
  onClose,
}: {
  /** The name beside the pin; none shows only the pin. */
  label?: string;
  selected: boolean;
  title: string;
  meta: string;
  status: { label: string; tone: Tone };
  value: string;
  onSelect: () => void;
  onClose: () => void;
}) {
  return (
    <span
      onKeyDown={(event) => {
        if (selected && event.key === "Escape") {
          event.stopPropagation();
          onClose();
        }
      }}
      className="relative inline-flex items-center gap-1.5 text-12 leading-4"
    >
      <button
        type="button"
        aria-label={title}
        aria-expanded={selected}
        onClick={selected ? onClose : onSelect}
        className={cx(
          "shrink-0 cursor-pointer rounded-full border-0 bg-ink p-0 shadow-[0_0_0_2px_var(--bg)]",
          selected ? "-m-0.5 size-3" : "size-2",
        )}
      />
      {label && <span className="rounded-[3px] bg-subtle px-[3px] text-text-2">{label}</span>}
      {selected && (
        <span className="absolute top-[-12px] left-[14px] z-[2] flex w-[220px] flex-col gap-0.5 rounded-[8px] border border-line-2 bg-bg px-3 py-2.5 text-13 text-text">
          <span className="font-medium">{title}</span>
          <span className="text-text-3">{meta}</span>
          <StatusValue label={status.label} tone={status.tone} />
          <span className="tabular-nums">{value}</span>
        </span>
      )}
    </span>
  );
}
