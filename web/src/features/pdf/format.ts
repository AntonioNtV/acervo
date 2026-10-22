import type { Lang } from "../../i18n";

const UNITS = ["B", "KB", "MB", "GB"];

function locale(lang: Lang) {
  return lang === "en" ? "en" : "pt-BR";
}

export function formatSize(bytes: number, lang: Lang): string {
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const number = new Intl.NumberFormat(locale(lang), { maximumFractionDigits: unit === 0 ? 0 : 1 }).format(value);
  return `${number} ${UNITS[unit]}`;
}

export function formatDate(iso: string, lang: Lang): string {
  return new Intl.DateTimeFormat(locale(lang), { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
}

/** `Condições Gerais 2026.pdf` → name and extension, so the extension can be shown in gray. */
export function splitExt(title: string): { name: string; ext?: string } {
  const dot = title.lastIndexOf(".");
  return dot > 0 ? { name: title.slice(0, dot), ext: title.slice(dot + 1) } : { name: title };
}
