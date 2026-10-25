import type { PageVersion } from "../../api/client";
import { locale, useI18n, type Lang } from "../../i18n";

type T = ReturnType<typeof useI18n>["t"];

export function timeOf(iso: string, lang: Lang): string {
  return new Date(iso).toLocaleTimeString(locale(lang), { hour: "2-digit", minute: "2-digit" });
}

export function dateOf(iso: string, lang: Lang): string {
  return new Date(iso).toLocaleDateString(locale(lang), { day: "numeric", month: "short" });
}

/** "Hoje", "Ontem" or "14 de outubro". */
export function dayLabel(iso: string, lang: Lang, t: T): string {
  const date = new Date(iso);
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  if (date.toDateString() === new Date().toDateString()) return t("page.history.today");
  if (date.toDateString() === yesterday.toDateString()) return t("page.history.yesterday");
  return date.toLocaleDateString(locale(lang), { day: "numeric", month: "long" });
}

export function versionsText(t: T, n: number): string {
  return n === 1 ? t("page.versions.one") : t("page.versions.other", { n });
}

/** How long the editing session behind a version lasted; null when it did not come from one. */
export function spanText(t: T, version: PageVersion): string | null {
  if (!version.edit_started_at || !version.edit_ended_at) return null;
  const minutes = Math.round((Date.parse(version.edit_ended_at) - Date.parse(version.edit_started_at)) / 60000);
  return minutes < 1 ? t("page.history.spanShort") : t("page.history.span", { n: minutes });
}

/** A version's line under its time: how long its editing session lasted, when it came from one. */
export function AuthorLine({ children }: { children?: string | null }) {
  return <span className="text-12 text-text-3">{children}</span>;
}
