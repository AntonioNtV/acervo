import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { locale, useI18n } from "../i18n";
import { cx } from "./cx";
import { Icon } from "./Icon";
import { IconButton } from "./IconButton";

/** A date as "YYYY-MM-DD", read as a local calendar day so no time zone moves it. */
function parse(iso: string): Date {
  const [y = 0, m = 1, d = 1] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function iso(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function addDays(day: string, n: number): string {
  const date = parse(day);
  date.setDate(date.getDate() + n);
  return iso(date);
}

const STEPS: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };

/**
 * One month to pick a date, or a period in `range` mode: the first click starts the period, the second ends it.
 * The caller places the panel; Escape closes it.
 */
export function DatePicker({
  mode,
  value,
  end = null,
  today = iso(new Date()),
  reminder = false,
  onChange,
  onReminder,
  onClose,
}: {
  mode: "single" | "range";
  /** The chosen day, or the start of the period. */
  value: string | null;
  /** The end of the period (range mode). */
  end?: string | null;
  today?: string;
  reminder?: boolean;
  onChange: (value: string, end: string | null) => void;
  /** Given when the date can carry a reminder: shows the "remind me on the day" row. */
  onReminder?: (reminder: boolean) => void;
  onClose: () => void;
}) {
  const { t, lang } = useI18n();
  const [focused, setFocused] = useState(value ?? today);
  const [shown, setShown] = useState(() => (value ?? today).slice(0, 7));
  const panel = useRef<HTMLDivElement>(null);
  const tabbable = focused.startsWith(shown) ? focused : `${shown}-01`;
  const focusDay = (day: string) => panel.current?.querySelector<HTMLElement>(`[data-day="${day}"]`)?.focus();
  const first = parse(`${shown}-01`);
  const days = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
  const last = end ?? value;
  // ISO strings compare as dates.
  const inRange = (day: string) => mode === "range" && !!value && !!end && day > value && day < end;

  const title = new Intl.DateTimeFormat(locale(lang), { month: "long", year: "numeric" }).format(first);
  const weekday = new Intl.DateTimeFormat(locale(lang), { weekday: "narrow" });
  const long = new Intl.DateTimeFormat(locale(lang), { day: "numeric", month: "long", year: "numeric" });

  const month = (step: number) => {
    const date = new Date(first.getFullYear(), first.getMonth() + step, 1);
    setShown(iso(date).slice(0, 7));
  };

  const pick = (day: string) => {
    if (mode === "single") onChange(day, null);
    else if (value && !end) onChange(day < value ? day : value, day < value ? value : day);
    else onChange(day, null);
  };

  useEffect(() => {
    panel.current?.querySelector<HTMLElement>("[data-day][tabindex='0']")?.focus();
  }, []);

  const onKeyDown = (event: KeyboardEvent) => {
    const step = STEPS[event.key];
    if (!step) return;
    event.preventDefault();
    const next = addDays(focused, step);
    setFocused(next);
    setShown(next.slice(0, 7));
    // The day's button exists after the render that may switch the month.
    requestAnimationFrame(() => focusDay(next));
  };

  return (
    <div
      ref={panel}
      role="dialog"
      aria-label={t(mode === "range" ? "pickers.date.range" : "pickers.date.single")}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.stopPropagation();
          onClose();
        }
      }}
      className="w-[252px] rounded-[8px] border border-line-2 bg-bg p-2 text-13 text-text"
    >
      <div className="flex items-center justify-between pt-0 pr-0.5 pb-1.5 pl-1">
        <span className="font-medium">{title.charAt(0).toUpperCase() + title.slice(1)}</span>
        <span className="inline-flex gap-0.5">
          <IconButton size="sm" aria-label={t("pickers.date.prev")} onClick={() => month(-1)}>
            <Icon name="chevronLeft" size={14} />
          </IconButton>
          <IconButton size="sm" aria-label={t("pickers.date.next")} onClick={() => month(1)}>
            <Icon name="chevronRight" size={14} />
          </IconButton>
        </span>
      </div>
      <div className="grid grid-cols-[repeat(7,32px)] gap-y-0.5 text-12 tabular-nums">
        {Array.from({ length: 7 }, (_, i) => (
          // 2026-11-01 is a Sunday, so these are Sunday to Saturday.
          <span key={i} aria-hidden className="flex h-7 items-center justify-center text-text-3">
            {weekday.format(new Date(2026, 10, 1 + i))}
          </span>
        ))}
        {Array.from({ length: first.getDay() }, (_, i) => (
          <span key={`pad${i}`} />
        ))}
        {Array.from({ length: days }, (_, i) => {
          const day = `${shown}-${String(i + 1).padStart(2, "0")}`;
          const on = day === value || day === last;
          return (
            <span key={day} className={cx("flex h-7 items-center justify-center", inRange(day) && "bg-accent-soft")}>
              <button
                type="button"
                data-day={day}
                aria-label={long.format(parse(day))}
                aria-pressed={on}
                aria-current={day === today ? "date" : undefined}
                tabIndex={day === tabbable ? 0 : -1}
                onClick={() => pick(day)}
                onKeyDown={onKeyDown}
                onFocus={() => setFocused(day)}
                className={cx(
                  "size-7 cursor-pointer rounded-full border-0 bg-transparent p-0 text-12 text-text tabular-nums",
                  on ? "bg-ink font-medium text-on-ink" : "hover:bg-subtle",
                  day === today && !on && "shadow-[inset_0_0_0_1px_var(--ink)]",
                )}
              >
                {i + 1}
              </button>
            </span>
          );
        })}
      </div>
      {onReminder && (
        <>
          <div className="my-1 h-px bg-line" />
          <button
            type="button"
            role="switch"
            aria-checked={reminder}
            onClick={() => onReminder(!reminder)}
            className="flex h-[30px] w-full cursor-pointer items-center gap-2.5 rounded-[6px] border-0 bg-transparent px-2.5 text-left text-13 text-text hover:bg-subtle aria-checked:bg-subtle"
          >
            <span className="inline-flex text-text-2">
              <Icon name="recent" size={14} />
            </span>
            {t("pickers.date.remind")}
            {reminder && (
              <span className="ml-auto inline-flex text-text-2">
                <Icon name="check" size={14} />
              </span>
            )}
          </button>
        </>
      )}
    </div>
  );
}
