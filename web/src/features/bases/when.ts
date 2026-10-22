import type { Lang } from "../../i18n";

const steps: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 3600],
  ["month", 30 * 24 * 3600],
  ["week", 7 * 24 * 3600],
  ["day", 24 * 3600],
  ["hour", 3600],
  ["minute", 60],
];

/** "ontem", "há 2 semanas", "agora" — the coarsest unit that fits. */
export function relativeTime(iso: string, lang: Lang, now = Date.now()): string {
  const format = new Intl.RelativeTimeFormat(lang === "en" ? "en" : "pt-BR", { numeric: "auto" });
  const seconds = (new Date(iso).getTime() - now) / 1000;
  for (const [unit, size] of steps) {
    if (Math.abs(seconds) >= size) return format.format(Math.round(seconds / size), unit);
  }
  return format.format(0, "second");
}

export function fullDate(iso: string, lang: Lang): string {
  return new Date(iso).toLocaleString(lang === "en" ? "en" : "pt-BR", { dateStyle: "long", timeStyle: "short" });
}
