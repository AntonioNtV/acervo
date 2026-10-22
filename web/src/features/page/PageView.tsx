import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useNode, useVersions, type NodeDetail } from "../../api/queries";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { cx } from "../../ui/cx";
import { Dot } from "../../ui/Dot";
import { TextTabs } from "../../ui/TextTabs";
import { Conflict } from "./Conflict";
import { dateOf, versionsText } from "./format";
import { History } from "./History";
import { Markdown } from "./Markdown";
import { SourceEditor } from "./SourceEditor";
import { useEditing } from "./useEditing";

type Mode = "read" | "edit" | "split";

function useNow(ticking: boolean) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    if (!ticking) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [ticking]);
  return now;
}

function Page({ kbId, node, page }: { kbId: string; node: NodeDetail; page: NonNullable<NodeDetail["page"]> }) {
  const { t, lang } = useI18n();
  const [mode, setMode] = useState<Mode>("read");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [draftSettled, setDraftSettled] = useState(false);
  const [resumes, setResumes] = useState(0);
  const editing = useEditing(node.id, page);
  const versions = useVersions(node.id);
  const now = useNow(editing.savedAt !== null);
  const toRead = () => setMode("read");

  const parent = node.path.split("/").slice(0, -1).join(" / ");
  const lastEdit = versions.data?.[0]?.created_at;
  const draft = !editing.editing && !draftSettled ? page.draft : null;

  let status: string | null = null;
  if (editing.savedAt !== null) {
    const seconds = Math.max(0, Math.round((now - editing.savedAt) / 1000));
    status = seconds < 60 ? t("page.saved.seconds", { n: seconds }) : t("page.saved.minutes", { n: Math.floor(seconds / 60) });
  } else if (editing.dirty) {
    status = t("page.unsaved");
  }

  const source = (
    <SourceEditor
      key={`${editing.base}:${resumes}`}
      value={editing.text}
      label={t("page.source")}
      onChange={editing.change}
    />
  );
  const preview = <Markdown markdown={editing.text} links={page.links} kbId={kbId} />;

  return (
    <div className="flex min-h-full">
      <div className="min-w-0 flex-1">
        <div className={cx("mx-auto box-border px-14 pt-10 pb-16", mode === "split" ? "max-w-[1280px]" : "max-w-[720px]")}>
          <div className="flex flex-wrap items-center justify-between gap-3 text-12 text-text-3">
            <span>{parent}</span>
            <span className="flex items-center gap-4">
              <TextTabs<Mode>
                label={t("page.mode")}
                value={mode}
                onChange={setMode}
                options={[
                  { value: "read", label: t("page.read") },
                  { value: "edit", label: t("page.edit") },
                  { value: "split", label: t("page.split") },
                ]}
              />
              {editing.saveFailed ? <span className="text-err">{t("page.saveFailed")}</span> : status && <span>{status}</span>}
              {(mode !== "read" || editing.editing) && (
                <Button variant="ink" size="sm" disabled={editing.saving} onClick={() => editing.conclude(toRead)}>
                  {t("page.done")}
                </Button>
              )}
              <Button variant="quiet" size="sm" aria-pressed={historyOpen} onClick={() => setHistoryOpen(!historyOpen)}>
                {t("page.history")}
              </Button>
            </span>
          </div>
          <h1 className="mt-7 mb-1.5 text-32 font-medium tracking-[-0.035em]">{node.title}</h1>
          <div className="text-12 text-text-3">
            {lastEdit && `${t("page.edited", { date: dateOf(lastEdit, lang) })} · `}
            {versionsText(t, node.versions)}
          </div>
          {draft && (
            <div className="mt-4 flex flex-wrap items-center gap-3 border-y border-line py-2.5">
              <Dot tone="warn">{t("page.draft.found", { date: dateOf(draft.updated_at, lang) })}</Dot>
              <span className="ml-auto flex gap-1.5">
                <Button
                  size="sm"
                  onClick={() => {
                    editing.resume(draft);
                    setResumes(resumes + 1);
                    setDraftSettled(true);
                    if (mode === "read") setMode("edit");
                  }}
                >
                  {t("page.draft.continue")}
                </Button>
                <Button
                  variant="quiet"
                  size="sm"
                  onClick={() => {
                    editing.discard();
                    setDraftSettled(true);
                  }}
                >
                  {t("page.draft.discard")}
                </Button>
              </span>
            </div>
          )}
          {mode === "read" && <div className="mt-3">{preview}</div>}
          {mode === "edit" && <div className="mt-6">{source}</div>}
          {mode === "split" && (
            <div className="mt-6 grid grid-cols-2 gap-10">
              <div className="min-w-0">
                <span className="mb-3 block text-12 text-text-3">{t("page.markdown")}</span>
                {source}
              </div>
              <div className="min-w-0">
                <span className="mb-3 block text-12 text-text-3">{t("page.preview")}</span>
                {preview}
              </div>
            </div>
          )}
        </div>
      </div>
      {historyOpen && (
        <History nodeId={node.id} editingNow={editing.dirty} onClose={() => setHistoryOpen(false)} />
      )}
      <Conflict
        stale={editing.conflict}
        busy={editing.saving}
        onKeepMine={() => editing.conclude(toRead, true)}
        onDiscard={() => {
          editing.discard();
          toRead();
        }}
        onClose={editing.dismissConflict}
      />
    </div>
  );
}

/** A page: Ler · Editar · Dividir, its draft, "Concluir" and its history. Other kinds belong to other views. */
export function PageView() {
  const { kbId = "", nodeId = "" } = useParams();
  const { t } = useI18n();
  const node = useNode(nodeId);
  if (node.isError) return <p className="px-14 pt-10 text-text-3">{t("page.error")}</p>;
  if (node.data?.kind !== "page" || !node.data.page) return null;
  return <Page key={nodeId} kbId={kbId} node={node.data} page={node.data.page} />;
}
