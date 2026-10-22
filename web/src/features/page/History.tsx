import { useState } from "react";
import { useRestoreVersion, useVersionDiff, useVersions, type Version } from "../../api/queries";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { cx } from "../../ui/cx";
import { AuthorLine, dayLabel, timeOf, versionsText } from "./format";
import { DiffLines } from "./DiffLines";

function VersionDiff({ nodeId, versionId }: { nodeId: string; versionId: string }) {
  const diff = useVersionDiff(nodeId, versionId);
  if (!diff.data) return null;
  return (
    <div className="-mx-3 rounded-[7px] border border-line">
      <DiffLines lines={diff.data.lines} />
    </div>
  );
}

function Row({ time, highlighted, children }: { time: string; highlighted?: boolean; children: React.ReactNode }) {
  return (
    <li className={cx("grid grid-cols-[44px_minmax(0,1fr)] gap-3 border-t border-line px-[18px] py-3", highlighted && "bg-subtle")}>
      <span className="tabular-nums">{time}</span>
      <div className="flex min-w-0 flex-col gap-0.5">{children}</div>
    </li>
  );
}

/** Every version, newest first and grouped by day. No version is ever changed or deleted. */
export function History({ nodeId, editingNow, onClose }: { nodeId: string; editingNow: boolean; onClose: () => void }) {
  const { t, lang } = useI18n();
  const versions = useVersions(nodeId);
  const restore = useRestoreVersion(nodeId);
  const [open, setOpen] = useState<string | null>(null);
  const list = versions.data ?? [];

  const days: { label: string; items: { version: Version; number: number }[] }[] = [];
  list.forEach((version, i) => {
    const label = dayLabel(version.created_at, lang, t("page.history.today"));
    if (days.at(-1)?.label !== label) days.push({ label, items: [] });
    days.at(-1)!.items.push({ version, number: list.length - i });
  });
  const today = t("page.history.today");
  if (editingNow && days[0]?.label !== today) days.unshift({ label: today, items: [] });

  return (
    <aside
      aria-label={t("page.history")}
      className="sticky top-0 flex max-h-screen w-[320px] shrink-0 flex-col self-stretch overflow-y-auto border-l border-line"
    >
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-line pr-2 pl-[18px]">
        <span className="font-medium">{t("page.history")}</span>
        <Button variant="quiet" size="sm" icon aria-label={t("page.close")} onClick={onClose}>
          <svg viewBox="0 0 24 24" width={15} height={15} aria-hidden="true" className="fill-none stroke-current stroke-[1.5]">
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        </Button>
      </div>
      {days.map((day, d) => (
        <section key={day.label} aria-label={day.label}>
          <span className="block px-[18px] pt-3.5 pb-1.5 text-12 text-text-3">{day.label}</span>
          <ul className="m-0 list-none p-0">
            {d === 0 && editingNow && (
              <Row time={timeOf(new Date().toISOString(), lang)}>
                <span>{t("page.history.now")}</span>
                <span className="text-12 text-text-3">
                  {t("page.author.user")} · {t("page.history.unsaved")}
                </span>
              </Row>
            )}
            {day.items.map(({ version, number }) => {
              const current = number === list.length;
              const showing = open === version.id;
              return (
                <Row key={version.id} time={timeOf(version.created_at, lang)} highlighted={showing}>
                  <span>{t(current ? "page.history.current" : "page.history.version", { n: number })}</span>
                  <AuthorLine author={version.author} />
                  <span className="mt-1 flex gap-3.5 text-12">
                    <button
                      type="button"
                      onClick={() => setOpen(showing ? null : version.id)}
                      className="cursor-pointer border-0 bg-transparent p-0 text-text"
                    >
                      {t(showing ? "page.history.hideDiff" : "page.history.diff")}
                    </button>
                    {!current && (
                      <button
                        type="button"
                        disabled={restore.isPending}
                        onClick={() => restore.mutate(version.id)}
                        className="cursor-pointer border-0 bg-transparent p-0 text-text-3 enabled:hover:text-text"
                      >
                        {t("page.history.restore")}
                      </button>
                    )}
                  </span>
                  {showing && (
                    <div className="mt-2">
                      <VersionDiff nodeId={nodeId} versionId={version.id} />
                    </div>
                  )}
                </Row>
              );
            })}
          </ul>
        </section>
      ))}
      <div className="mt-auto border-t border-line px-[18px] py-3 text-12 text-text-3">
        {t("page.history.footer", { versions: versionsText(t, list.length) })}
      </div>
    </aside>
  );
}
