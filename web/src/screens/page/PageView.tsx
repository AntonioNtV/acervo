import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { NodeDetail, PageVersion } from "../../api/client";
import { BlockEditor, type LinkTarget } from "../../editor/BlockEditor";
import { normalizeLinkTarget, useRestorePageVersion } from "../../data/pages";
import { ApiError } from "../../data/request";
import { useChildren, useCreateNode, useRenameNode } from "../../data/tree";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { FileName } from "../../ui/FileName";
import { Icon } from "../../ui/Icon";
import { IconButton } from "../../ui/IconButton";
import { splitExt } from "../../ui/names";
import { TopBar } from "../shell/TopBar";
import { dateOf, dayLabel, timeOf, versionsText } from "./format";
import { History, VersionText } from "./History";
import { useAutosave } from "./useAutosave";

const RENAME_DELAY_MS = 1000;

type Page = NonNullable<NodeDetail["page"]>;

/** The title as the page's first line: it renames the node a second after typing stops. */
function Title({ node }: { node: NodeDetail }) {
  const { t } = useI18n();
  const [title, setTitle] = useState(node.title);
  const { mutate: rename, error } = useRenameNode();

  useEffect(() => {
    const next = title.trim();
    if (!next || next === node.title) return;
    const timer = setTimeout(() => rename({ nodeId: node.id, title: next }), RENAME_DELAY_MS);
    return () => clearTimeout(timer);
  }, [title, node.id, node.title, rename]);

  return (
    <>
      <h1 className="m-0">
        <input
          aria-label={t("page.title")}
          value={title}
          placeholder={t("page.untitled")}
          onChange={(event) => setTitle(event.target.value)}
          className="w-full border-0 bg-transparent p-0 text-32 font-medium tracking-[-0.025em] text-text outline-none placeholder:text-ghost"
        />
      </h1>
      {error && (
        <p role="alert" className="m-0 mt-1 text-12 text-err">
          {t(error instanceof ApiError && error.code === "title_taken" ? "page.title.taken" : "page.title.failed")}
        </p>
      )}
    </>
  );
}

function PageScreen({ node, page }: { node: NodeDetail; page: Page }) {
  const { t, lang } = useI18n();
  const kbId = node.kb_id;
  const autosave = useAutosave(node.id, page);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [selected, setSelected] = useState<PageVersion | null>(null);
  const [editingNow, setEditingNow] = useState(false);
  const restore = useRestorePageVersion(node.id);
  const children = useChildren(kbId, node.id).data ?? [];
  const { mutateAsync: createNode } = useCreateNode(kbId);

  const childPages = children.filter((child) => child.kind === "page");
  const href = (id: string) => `/kbs/${kbId}/n/${id}`;

  // A sub-page just created is a child before the next save resolves its link.
  const resolveLink = (title: string): LinkTarget => {
    const key = normalizeLinkTarget(title);
    const linked = page.links[key];
    const resolved =
      linked && linked !== "missing" ? linked : childPages.find((child) => normalizeLinkTarget(child.title) === key)?.id;
    if (!resolved) return "missing";
    if (resolved === "ambiguous") return resolved;
    return { href: href(resolved) };
  };

  /** A page under this one, named "Sem título", "Sem título 2", … so it never clashes with a sibling. */
  const createSubPage = async (title: string): Promise<string> => {
    const taken = new Set(childPages.map((child) => normalizeLinkTarget(child.title)));
    for (let n = 1; ; n++) {
      const candidate = n === 1 ? title : `${title} ${n}`;
      if (taken.has(normalizeLinkTarget(candidate))) continue;
      try {
        return (await createNode({ kind: "page", parent_id: node.id, title: candidate })).title;
      } catch (error) {
        if (!(error instanceof ApiError && error.code === "title_taken")) throw error;
      }
    }
  };

  const change = (markdown: string) => {
    autosave.change(markdown);
    if (historyOpen) setEditingNow(true);
  };

  const openHistory = async () => {
    // The history cuts the working text as a version: what is pending goes first.
    await autosave.flush();
    setEditingNow(false);
    setHistoryOpen(true);
  };

  const closeHistory = () => {
    setHistoryOpen(false);
    setSelected(null);
  };

  const restoreSelected = async (version: PageVersion) => {
    await autosave.flush();
    restore.mutate(version.id, {
      onSuccess: (read) => {
        autosave.replace(read.markdown, read.revision);
        setSelected(null);
        setEditingNow(false);
      },
    });
  };

  const statusText = {
    saving: t("page.saving"),
    saved: t("page.saved"),
    failed: <span className="text-err">{t("page.saveFailed")}</span>,
  }[autosave.status];

  return (
    <>
      <TopBar
        kbId={kbId}
        nodeId={node.id}
        status={
          selected ? (
            <span className="text-13 text-text-2">
              {t("page.history.viewing", {
                when: `${dayLabel(selected.created_at, lang, t).toLowerCase()}, ${timeOf(selected.created_at, lang)}`,
              })}
            </span>
          ) : (
            statusText
          )
        }
        actions={
          selected ? (
            <span className="flex items-center gap-2 pr-1">
              <Button size="sm" onClick={() => setSelected(null)}>
                {t("page.history.back")}
              </Button>
              <Button variant="ink" size="sm" disabled={restore.isPending} onClick={() => void restoreSelected(selected)}>
                {t("page.history.restore")}
              </Button>
            </span>
          ) : (
            <IconButton
              aria-label={t("page.history")}
              aria-pressed={historyOpen}
              onClick={() => (historyOpen ? closeHistory() : void openHistory())}
            >
              <Icon name="recent" />
            </IconButton>
          )
        }
      />
      <div className="flex min-h-full">
        <div className="min-w-0 flex-1">
          <div className="mx-auto box-border w-full max-w-[720px] px-8 pt-10 pb-30">
            <div className="mb-1 text-13 text-ghost">
              {t("page.edited", { date: dateOf(page.saved_at, lang) })} · {versionsText(t, node.versions)}
            </div>
            <Title node={node} />
            {autosave.reloaded && (
              <div role="status" className="mt-4 flex items-start gap-2 border-y border-line py-2 text-13 text-text-2">
                <span aria-hidden="true" className="mt-[7px] size-1.5 shrink-0 rounded-full bg-warn" />
                <span className="flex-1">{t("page.reloaded")}</span>
                <IconButton size="sm" aria-label={t("page.reloaded.close")} onClick={autosave.dismissReloaded}>
                  <Icon name="close" size={14} />
                </IconButton>
              </div>
            )}
            {selected && (
              <div className="mt-5">
                <VersionText nodeId={node.id} versionId={selected.id} />
              </div>
            )}
            <div hidden={selected !== null} className="mt-5">
              <BlockEditor
                key={autosave.opened.key}
                markdown={autosave.opened.markdown}
                onChange={change}
                resolveLink={resolveLink}
                onCreateSubPage={createSubPage}
                pageTitles={childPages.map((child) => child.title)}
              />
              {children.length > 0 && (
                <nav aria-label={t("page.children")} className="mt-10 border-t border-line pt-3">
                  <span className="block pb-1 text-12 text-text-3">{t("page.children")}</span>
                  <ul className="m-0 flex list-none flex-col p-0">
                    {children.map((child) => {
                      const { name, ext } = child.kind === "file" ? splitExt(child.title) : { name: child.title, ext: undefined };
                      return (
                        <li key={child.id}>
                          <Link
                            to={href(child.id)}
                            className="-mx-1.5 flex items-center gap-2 rounded-[6px] px-1.5 py-1 text-15 text-text no-underline hover:bg-subtle"
                          >
                            <span className="text-text-3">
                              <Icon name={child.kind} />
                            </span>
                            <FileName title={name} ext={ext} />
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                </nav>
              )}
            </div>
          </div>
        </div>
        {historyOpen && (
          <History
            nodeId={node.id}
            selected={selected}
            editingNow={editingNow}
            onSelect={setSelected}
            onClose={closeHistory}
          />
        )}
      </div>
    </>
  );
}

/** A page: its title, its blocks saved as they are typed, its sub-pages and its history. */
export function PageView({ node }: { node: NodeDetail }) {
  if (!node.page) return null;
  return <PageScreen node={node} page={node.page} />;
}
