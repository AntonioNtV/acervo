import type { DiffLine, PageVersion } from "../../api/client";
import { useMe } from "../../data/account";
import { usePageVersionDiff, usePageVersions } from "../../data/pages";
import { useI18n } from "../../i18n";
import { Icon } from "../../ui/Icon";
import { IconButton } from "../../ui/IconButton";
import { cx } from "../../ui/cx";
import { AuthorLine, authorText, dayLabel, spanText, timeOf } from "./format";

const rowClass = "flex w-full flex-col gap-0.5 border-0 border-l-2 border-transparent bg-transparent px-4 py-2.5 text-left";

/**
 * The versions by day, newest first. Opening it cuts the working text as a version (the API does it on reading), so
 * the newest entry is the text on the page; "Agora" stands for what was typed since.
 */
export function History({
  nodeId,
  selected,
  editingNow,
  onSelect,
  onClose,
}: {
  nodeId: string;
  selected: PageVersion | null;
  editingNow: boolean;
  onSelect: (version: PageVersion | null) => void;
  onClose: () => void;
}) {
  const { t, lang } = useI18n();
  const versions = usePageVersions(nodeId);
  const meId = useMe().data?.id;

  const days: { label: string; items: PageVersion[] }[] = [];
  for (const version of versions.data ?? []) {
    const label = dayLabel(version.created_at, lang, t);
    if (days.at(-1)?.label !== label) days.push({ label, items: [] });
    days.at(-1)!.items.push(version);
  }
  const today = t("page.history.today");
  if (editingNow && days[0]?.label !== today) days.unshift({ label: today, items: [] });

  return (
    <aside
      aria-label={t("page.history")}
      className="sticky top-0 flex max-h-screen w-[320px] shrink-0 flex-col self-stretch overflow-y-auto border-l border-line bg-bg"
    >
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-line pr-2 pl-4">
        <span className="font-medium">{t("page.history")}</span>
        <IconButton aria-label={t("page.history.close")} onClick={onClose}>
          <Icon name="close" />
        </IconButton>
      </div>
      {days.map((day, d) => (
        <section key={day.label} aria-label={day.label}>
          <span className="block px-4 pt-4 pb-1 text-12 text-text-3">{day.label}</span>
          <ul className="m-0 list-none p-0">
            {d === 0 && editingNow && (
              <li className={rowClass}>
                <span className="font-medium">{t("page.history.now")}</span>
                <span className="text-12 text-text-3">
                  {t("page.history.editing")}
                </span>
              </li>
            )}
            {day.items.map((version) => {
              const on = selected?.id === version.id;
              return (
                <li key={version.id}>
                  <button
                    type="button"
                    aria-pressed={on}
                    onClick={() => onSelect(on ? null : version)}
                    className={cx(rowClass, "cursor-pointer text-text hover:bg-side", on && "border-l-ink bg-subtle hover:bg-subtle")}
                  >
                    <span className="font-medium tabular-nums">{timeOf(version.created_at, lang)}</span>
                    <AuthorLine>{[authorText(t, version, meId), spanText(t, version)].filter(Boolean).join(" · ")}</AuthorLine>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
      <div className="mt-auto border-t border-line px-4 py-3 text-12 text-text-3">{t("page.history.footer")}</div>
    </aside>
  );
}

const HEADING = /^(#{1,3})\s+(.*)$/;
const headingClass = ["", "mt-7 text-24 font-medium", "mt-5 text-20 font-medium", "mt-4 text-15 font-medium"];

function Line({ line }: { line: DiffLine }) {
  const heading = HEADING.exec(line.text);
  const text = heading ? heading[2] : line.text;
  return (
    <div
      data-op={line.op}
      className={cx("min-h-[26px] whitespace-pre-wrap", heading && headingClass[heading[1]!.length])}
    >
      <span
        className={cx(
          line.op === "add" && "rounded-[3px] bg-add",
          line.op === "del" && "rounded-[3px] bg-del text-text-2 line-through decoration-err",
        )}
      >
        {text}
      </span>
    </div>
  );
}

/** A version as it was, in the page, with what came in with it and what went out marked. */
export function VersionText({ nodeId, versionId }: { nodeId: string; versionId: string }) {
  const { t } = useI18n();
  const diff = usePageVersionDiff(nodeId, versionId);
  return (
    <div>
      <div className="mb-5 flex gap-3.5 text-13 text-text-3">
        <span>
          <span className="rounded-[3px] bg-add px-0.5">{t("page.history.legend.add")}</span> {t("page.history.legend.addText")}
        </span>
        <span>
          <span className="rounded-[3px] bg-del px-0.5">{t("page.history.legend.del")}</span> {t("page.history.legend.delText")}
        </span>
      </div>
      <div className="text-[16px] leading-[26px]">
        {diff.data?.lines.map((line, i) => <Line key={i} line={line} />)}
      </div>
    </div>
  );
}
