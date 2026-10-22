import type { Kb } from "../../api/client";
import { useRestoreKb, useTrashedKbs } from "../../data/kbs";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { fullDate, relativeTime } from "./when";

function TrashedBase({ kb }: { kb: Kb }) {
  const { t, lang } = useI18n();
  const restore = useRestoreKb();
  const when = kb.deleted_at ?? "";

  return (
    <li className="flex min-h-16 items-center gap-5 border-b border-line py-3">
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="font-medium">{kb.name}</span>
        {kb.description && <span className="truncate text-text-3">{kb.description}</span>}
      </div>
      <time dateTime={when} title={fullDate(when, lang)} className="text-12 text-text-3 tabular-nums">
        {t("bases.trash.when", { when: relativeTime(when, lang) })}
      </time>
      {restore.isError && (
        <span role="alert" className="text-12 text-err">
          {t("bases.restore.error")}
        </span>
      )}
      <Button size="sm" disabled={restore.isPending} onClick={() => restore.mutate(kb.id)}>
        {t("bases.restore")}
      </Button>
    </li>
  );
}

export function TrashPage() {
  const { t } = useI18n();
  const trashed = useTrashedKbs();

  return (
    <>
      <h1 className="m-0 text-32 leading-[38px] font-medium tracking-[-0.035em]">
        {t("bases.trash.title")} {trashed.data && <span className="text-ghost">{trashed.data.length}</span>}
      </h1>
      <div className="mt-10">
        {trashed.isPending ? (
          <p className="m-0 text-text-3">{t("bases.loading")}</p>
        ) : trashed.isError ? (
          <div className="flex items-center gap-3">
            <p role="alert" className="m-0 text-err">
              {t("bases.trash.error")}
            </p>
            <Button size="sm" onClick={() => trashed.refetch()}>
              {t("bases.retry")}
            </Button>
          </div>
        ) : trashed.data.length === 0 ? (
          <p className="m-0 text-text-3">{t("bases.trash.empty")}</p>
        ) : (
          <ul className="m-0 list-none border-t border-line p-0">
            {trashed.data.map((kb) => (
              <TrashedBase key={kb.id} kb={kb} />
            ))}
          </ul>
        )}
      </div>
    </>
  );
}
