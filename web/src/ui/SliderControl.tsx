import type { CSSProperties } from "react";

/** A native range: the track in line-2, filled in ink up to the thumb, and the value written beside it. */
export function SliderControl({
  label,
  value,
  min,
  max,
  valueLabel,
  onChange,
  disabled,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  valueLabel: string;
  onChange: (value: number) => void;
  disabled?: boolean;
}) {
  const fraction = max > min ? (Math.min(max, Math.max(min, value)) - min) / (max - min) : 0;
  return (
    <div className={`inline-flex items-center gap-2 text-13 text-text ${disabled ? "opacity-50" : ""}`}>
      <input
        type="range"
        aria-label={label}
        aria-valuetext={valueLabel}
        min={min}
        max={max}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
        // The fill ends at the thumb's center, which travels 7 px inside each end of the track.
        style={
          {
            "--fill": `calc(7px + (100% - 14px) * ${fraction})`,
          } as CSSProperties
        }
        className={[
          "m-0 h-1 w-[240px] cursor-pointer appearance-none rounded-[2px] disabled:cursor-default",
          "bg-[linear-gradient(to_right,var(--ink)_var(--fill),var(--line-2)_var(--fill))]",
          "[&::-webkit-slider-thumb]:size-3.5 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-0 [&::-webkit-slider-thumb]:bg-ink [&::-webkit-slider-thumb]:shadow-[0_0_0_2px_var(--bg)]",
          "[&::-moz-range-thumb]:size-3.5 [&::-moz-range-thumb]:appearance-none [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:bg-ink [&::-moz-range-thumb]:shadow-[0_0_0_2px_var(--bg)]",
          "[&:active::-webkit-slider-thumb]:shadow-[0_0_0_2px_var(--bg),0_0_0_5px_var(--accent-soft)]",
          "[&:active::-moz-range-thumb]:shadow-[0_0_0_2px_var(--bg),0_0_0_5px_var(--accent-soft)]",
        ].join(" ")}
      />
      <b className="font-medium tabular-nums">{valueLabel}</b>
    </div>
  );
}
