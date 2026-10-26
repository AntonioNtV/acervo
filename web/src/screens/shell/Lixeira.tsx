import { useState } from "react";
import type { Kb, KbSummary } from "../../api/client";
import { useKbs, useRestoreKb, useTrashedKbs } from "../../data/kbs";
import { useKbTrash, useRestoreNode } from "../../data/tree";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { NodeName, useTreeErrorText } from "../base/names";
import { fullDate, relativeTime } from "../bases/when";
import { TopBar } from "./TopBar";

const rowClass = "flex min-h-14 items-center gap-5 border-b border-line py-2.5";

function TrashedBase({ kb }: { kb: Kb }) {
  const { t, lang } = useI18n();
  const restore = useRestoreKb();
  const when = kb.deleted_at ?? "";
  return (
    <li className={rowClass}>
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

/** What was trashed on its own inside one live base, with where it was; nothing when there is none. */
function BaseTrash({ kb }: { kb: KbSummary }) {
  const { t } = useI18n();
  const trash = useKbTrash(kb.id);
  const restore = useRestoreNode();
  const errorText = useTreeErrorText();
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null);
  const items = trash.data ?? [];
  if (items.length === 0 && !notice) return null;
  return (
    <section aria-label={kb.name} className="mt-10">
      <h2 className="m-0 mb-2 text-15 font-medium tracking-[-0.01em]">{kb.name}</h2>
      {notice && (
        <p role="status" className={notice.error ? "m-0 text-12 text-err" : "m-0 text-12 text-text-2"}>
          {notice.text}
        </p>
      )}
      <ul className="m-0 list-none border-t border-line p-0">
        {items.map((item) => (
          <li key={item.id} className={rowClass}>
            <span className="flex min-w-0 flex-1 flex-col">
              <NodeName node={item} className="truncate" />
              <span className="truncate text-12 text-text-3">{item.path}</span>
            </span>
            <Button
              size="sm"
              disabled={restore.isPending}
              onClick={() =>
                restore.mutate(item.id, {
                  onSuccess: (node) =>
                    setNotice({ text: t(node.to_root ? "base.bin.restoredToRoot" : "base.bin.restored", { name: node.title }) }),
                  onError: (e) => setNotice({ text: errorText(e), error: true }),
                })
              }
            >
              {t("base.bin.restore")}
            </Button>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** The current organization's bases in the Lixeira, then what each live base the person may edit has in its own. */
export function Lixeira() {
  const { t } = useI18n();
  const trashed = useTrashedKbs();
  const kbs = useKbs();
  return (
    <>
      <TopBar label={t("shell.trash")} />
      <div className="mx-auto w-full max-w-[720px] px-8 pt-14 pb-16">
        <h1 className="m-0 text-32 font-medium tracking-[-0.035em]">{t("shell.trash")}</h1>
        <section aria-label={t("shell.trash.bases")} className="mt-10">
          <h2 className="m-0 mb-2 text-15 font-medium tracking-[-0.01em]">{t("shell.trash.bases")}</h2>
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
            <p className="m-0 text-text-3">{t("shell.trash.noBases")}</p>
          ) : (
            <ul className="m-0 list-none border-t border-line p-0">
              {trashed.data.map((kb) => (
                <TrashedBase key={kb.id} kb={kb} />
              ))}
            </ul>
          )}
        </section>
        {kbs.data?.map((kb) => kb.my_role !== "reader" && <BaseTrash key={kb.id} kb={kb} />)}
      </div>
    </>
  );
}
