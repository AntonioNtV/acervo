import type { Version } from "../../api/queries";
import { AiMark } from "../../app/AiMark";
import { locale, useI18n, type Lang } from "../../i18n";

type T = ReturnType<typeof useI18n>["t"];

export function timeOf(iso: string, lang: Lang): string {
  return new Date(iso).toLocaleTimeString(locale(lang), { hour: "2-digit", minute: "2-digit" });
}

export function dateOf(iso: string, lang: Lang): string {
  return new Date(iso).toLocaleDateString(locale(lang), { day: "numeric", month: "short" });
}

export function dayLabel(iso: string, lang: Lang, today: string): string {
  const date = new Date(iso);
  if (date.toDateString() === new Date().toDateString()) return today;
  return date.toLocaleDateString(locale(lang), { day: "numeric", month: "long" });
}

export function versionsText(t: T, n: number): string {
  return n === 1 ? t("page.versions.one") : t("page.versions.other", { n });
}

/** Who wrote a version: the person, or (from F2) the chat, which is one of the few violet things. */
export function AuthorLine({ author }: { author: Version["author"] }) {
  const { t } = useI18n();
  if (author === "agent") {
    return (
      <span className="inline-flex items-center gap-[5px] text-12 text-ai-text">
        <AiMark size={12} />
        {t("page.author.agent")}
      </span>
    );
  }
  return <span className="text-12 text-text-3">{t("page.author.user")}</span>;
}
