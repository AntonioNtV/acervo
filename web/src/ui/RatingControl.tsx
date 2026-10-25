import type { KeyboardEvent } from "react";
import { useI18n } from "../i18n";
import { Icon } from "./Icon";

const STARS = [1, 2, 3, 4, 5];

/**
 * A rating of 0 to 5 as a radio group: a click or an arrow picks a star; clicking the chosen star, or going left of
 * the first, clears it to 0.
 */
export function RatingControl({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  const { t } = useI18n();

  function move(event: KeyboardEvent<HTMLDivElement>) {
    const step = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 }[event.key];
    if (!step) return;
    event.preventDefault();
    const next = Math.min(5, Math.max(0, value + step));
    (event.currentTarget.children[Math.max(next, 1) - 1] as HTMLElement).focus();
    if (next !== value) onChange(next);
  }

  return (
    <div role="radiogroup" aria-label={label} onKeyDown={move} className="inline-flex gap-0.5">
      {STARS.map((n) => (
        <button
          key={n}
          type="button"
          role="radio"
          aria-checked={n === value}
          aria-label={t(n === 1 ? "controls.stars.one" : "controls.stars.other", { n })}
          tabIndex={n === Math.max(value, 1) ? 0 : -1}
          onClick={() => onChange(n === value ? 0 : n)}
          className={`flex cursor-pointer border-0 bg-transparent p-0 ${n <= value ? "text-ink [&_svg]:fill-current" : "text-text-3"}`}
        >
          <Icon name="star" size={18} />
        </button>
      ))}
    </div>
  );
}
