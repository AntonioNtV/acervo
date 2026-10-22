import type { PageVersion } from "../../api/client";
import { AiMark } from "../../app/AiMark";
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

/** Who wrote a version: the person, or (from F2) the chat, which is one of the few violet things. */
export function AuthorLine({ author, children }: { author: PageVersion["author"]; children?: string | null }) {
  const { t } = useI18n();
  if (author === "agent") {
    return (
      <span className="inline-flex items-center gap-[5px] text-12 text-ai-text">
        <AiMark size={12} />
        {t("page.author.agent")}
        {children && ` · ${children}`}
      </span>
    );
  }
  return (
    <span className="text-12 text-text-3">
      {t("page.author.user")}
      {children && ` · ${children}`}
    </span>
  );
}
