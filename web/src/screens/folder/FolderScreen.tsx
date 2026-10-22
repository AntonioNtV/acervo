import { useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import type { NodeDetail, TreeNode } from "../../api/client";
import { useKbs } from "../../data/kbs";
import { useChildren, useCreateNode, useDescribeNode, useRenameNode } from "../../data/tree";
import { locale, useI18n, type Lang } from "../../i18n";
import { Button } from "../../ui/Button";
import { cx } from "../../ui/cx";
import { Icon } from "../../ui/Icon";
import { TextTabs } from "../../ui/TextTabs";
import { NodeName, useTreeErrorText } from "../base/names";
import { useStartUpload } from "../base/Upload";
import { relativeTime } from "../bases/when";
import { formatSize } from "../file/format";
import { TopBar } from "../shell/TopBar";

type Filter = "all" | "page" | "file";

const DAY = 24 * 3600 * 1000;
const columns =
  "grid grid-cols-[minmax(0,1fr)_28px] items-center gap-3 px-1.5 sm:grid-cols-[minmax(0,1fr)_140px_140px_28px]";

function UploadGlyph() {
  return (
    <svg
      viewBox="0 0 24 24"
      width={14}
      height={14}
      aria-hidden="true"
      className="shrink-0 fill-none stroke-current stroke-[1.5]"
    >
      <path d="M12 16V4M6 10l6-6 6 6M5 20h14" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** "agora", "há 3 horas" within a day; "14 de out." after. */
function edited(iso: string, lang: Lang, now = Date.now()): string {
  const then = new Date(iso);
  if (now - then.getTime() < DAY) return relativeTime(iso, lang, now);
  const sameYear = then.getFullYear() === new Date(now).getFullYear();
  return then.toLocaleDateString(locale(lang), {
    day: "numeric",
    month: "short",
    ...(sameYear ? {} : { year: "numeric" }),
  });
}

/** A folder opened: its header, its children filtered by kind, and where pages and files are added to it. */
export function FolderScreen({ node }: { node: NodeDetail }) {
  return <Folder kbId={node.kb_id} folder={node} />;
}

/** The base opened with no node chosen: its root, as a folder. */
export function BaseRootScreen() {
  const { kbId = "" } = useParams();
  return <Folder kbId={kbId} folder={null} />;
}

function Folder({ kbId, folder }: { kbId: string; folder: NodeDetail | null }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const kb = useKbs().data?.find((summary) => summary.id === kbId);
  const folderId = folder?.id ?? null;
  const title = folder ? folder.title : (kb?.name ?? "");
  const description = folder ? folder.description : (kb?.description ?? "");
  const children = useChildren(kbId, folderId);
  const create = useCreateNode(kbId);
  const startUpload = useStartUpload(kbId);
  const input = useRef<HTMLInputElement>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [over, setOver] = useState(false);

  const all = children.data ?? [];
  const pages = all.filter((child) => child.kind === "page");
  const files = all.filter((child) => child.kind === "file");
  const shown = filter === "all" ? all : filter === "page" ? pages : files;

  function newPage() {
    const taken = new Set(pages.map((page) => page.title));
    const base = t("folder.untitled");
    let name = base;
    for (let n = 2; taken.has(name); n++) name = `${base} ${n}`;
    create.mutate(
      { kind: "page", parent_id: folderId, title: name },
      { onSuccess: (page) => navigate(`/kbs/${kbId}/n/${page.id}`) },
    );
  }

  return (
    <>
      <TopBar kbId={kbId} nodeId={folderId ?? undefined} />
      <div
        className="mx-auto box-border max-w-[900px] px-4 pt-14 pb-[120px] sm:px-8"
        onDragOver={(event) => {
          if (!event.dataTransfer.types.includes("Files")) return;
          event.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(event) => {
          if (!event.dataTransfer.files.length) return;
          event.preventDefault();
          setOver(false);
          startUpload(Array.from(event.dataTransfer.files), folderId);
        }}
      >
        <div className="flex size-16 items-center justify-center rounded-[10px] bg-subtle text-text-2">
          <Icon name="folder" size={34} className="stroke-[1.3]" />
        </div>
        {folder ? <Title node={folder} /> : <h1 className={titleClass}>{title}</h1>}
        {folder ? (
          <Description node={folder} />
        ) : (
          description && <p className="m-0 mt-1.5 text-15 leading-6 text-text-2">{description}</p>
        )}

        <div className="mt-7 flex flex-wrap items-center justify-between gap-3">
          <TextTabs
            label={t("folder.filters")}
            value={filter}
            onChange={setFilter}
            options={[
              { value: "all", label: t("folder.all", { n: all.length }) },
              { value: "page", label: t("folder.pages", { n: pages.length }) },
              { value: "file", label: t("folder.files", { n: files.length }) },
            ]}
          />
          <div className="flex gap-1.5">
            <Button size="sm" onClick={() => input.current?.click()}>
              <UploadGlyph />
              {t("folder.upload")}
            </Button>
            <input
              ref={input}
              type="file"
              multiple
              hidden
              aria-label={t("folder.upload")}
              onChange={(event) => {
                startUpload(Array.from(event.target.files ?? []), folderId);
                event.target.value = "";
              }}
            />
            <Button size="sm" variant="ink" disabled={create.isPending} onClick={newPage}>
              <Icon name="plus" size={14} />
              {t("folder.new.page")}
            </Button>
          </div>
        </div>

        <div className="mt-7 border-t border-line">
          <div className={cx(columns, "min-h-8 border-b border-line text-12 text-text-3")}>
            <span>{t("folder.name")}</span>
            <span className="max-sm:hidden">{t("folder.edited")}</span>
            <span className="max-sm:hidden">{t("folder.inside")}</span>
            <span />
          </div>
          {children.isSuccess && shown.length === 0 && (
            <p className="m-0 border-b border-line px-1.5 py-3 text-13 text-text-3">{t("folder.empty")}</p>
          )}
          <ul className="m-0 list-none p-0">
            {shown.map((child) => (
              <li key={child.id}>
                <Row kbId={kbId} node={child} />
              </li>
            ))}
          </ul>
        </div>
        <div
          className={cx(
            "mt-5 flex items-center justify-center gap-2 rounded-[8px] border border-dashed p-[18px] text-13 text-text-3",
            over ? "border-ink bg-accent-soft" : "border-line-2",
          )}
        >
          <UploadGlyph />
          {t("folder.drop", { name: title })}
        </div>
      </div>
    </>
  );
}

const titleClass = "m-0 mt-4 text-[40px] leading-[48px] font-medium tracking-[-0.025em] break-words";

/** The folder's name, renamed in place: Enter or leaving the field saves, Esc gives up. */
/** The folder's description, edited in place; the person's text is locked against agents. */
function Description({ node }: { node: NodeDetail }) {
  const { t } = useI18n();
  const describe = useDescribeNode();
  const errorText = useTreeErrorText();
  const [draft, setDraft] = useState<string | null>(null);

  function commit() {
    const description = draft?.trim() ?? "";
    if (draft === null || description === (node.description ?? "")) return setDraft(null);
    describe.mutate({ nodeId: node.id, description }, { onSuccess: () => setDraft(null) });
  }

  if (draft === null) {
    return (
      <button
        type="button"
        onClick={() => {
          describe.reset();
          setDraft(node.description ?? "");
        }}
        className={cx(
          "mt-1.5 block cursor-text border-0 bg-transparent p-0 text-left font-[inherit] text-15 leading-6",
          node.description ? "text-text-2" : "text-ghost",
        )}
      >
        {node.description || t("folder.describe")}
      </button>
    );
  }
  return (
    <>
      <input
        autoFocus
        aria-label={t("folder.describe")}
        value={draft}
        maxLength={200}
        disabled={describe.isPending}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") commit();
          if (event.key === "Escape") setDraft(null);
        }}
        className="mt-1.5 block w-full border-0 bg-transparent p-0 font-[inherit] text-15 leading-6 text-text-2 outline-none"
      />
      {describe.isError && <p className="m-0 mt-1 text-12 text-err">{errorText(describe.error)}</p>}
    </>
  );
}

function Title({ node }: { node: NodeDetail }) {
  const { t } = useI18n();
  const rename = useRenameNode();
  const errorText = useTreeErrorText();
  const [draft, setDraft] = useState<string | null>(null);

  function commit() {
    const title = draft?.trim();
    if (!title || title === node.title) return setDraft(null);
    rename.mutate({ nodeId: node.id, title }, { onSuccess: () => setDraft(null) });
  }

  if (draft === null) {
    return (
      <h1 className={titleClass}>
        <button
          type="button"
          aria-label={t("folder.rename", { name: node.title })}
          onClick={() => {
            rename.reset();
            setDraft(node.title);
          }}
          className="cursor-text border-0 bg-transparent p-0 text-left font-[inherit] text-[length:inherit] leading-[inherit] tracking-[inherit] text-text"
        >
          {node.title}
        </button>
      </h1>
    );
  }
  return (
    <>
      <input
        autoFocus
        aria-label={t("folder.rename", { name: node.title })}
        aria-invalid={rename.isError || undefined}
        value={draft}
        disabled={rename.isPending}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") commit();
          if (event.key === "Escape") setDraft(null);
        }}
        className={cx(titleClass, "block w-full border-0 bg-transparent p-0 text-text outline-none")}
      />
      {rename.isError && <p className="m-0 mt-1 text-12 text-err">{errorText(rename.error)}</p>}
    </>
  );
}

function Row({ kbId, node }: { kbId: string; node: TreeNode }) {
  const { lang } = useI18n();
  return (
    <Link
      to={`/kbs/${kbId}/n/${node.id}`}
      className={cx(columns, "min-h-11 border-b border-line text-text no-underline hover:bg-side")}
    >
      <span className="flex min-w-0 items-center gap-2.5 text-15">
        <Icon name={node.kind} className="text-text-2" />
        <NodeName node={node} pageExt={false} className="truncate" />
      </span>
      <span className="text-13 whitespace-nowrap text-text-3 max-sm:hidden">{edited(node.updated_at, lang)}</span>
      <span className="text-13 whitespace-nowrap text-text-3 max-sm:hidden">
        {node.kind === "file" ? <FileHolds node={node} /> : <Holds node={node} />}
      </span>
      <span aria-hidden="true" className="text-13 text-text-3">
        ›
      </span>
    </Link>
  );
}

/** How many live things a folder or page holds, or a dash. */
function Holds({ node }: { node: TreeNode }) {
  const { t } = useI18n();
  const n = node.child_count;
  if (!n) return <>—</>;
  return <>{t(n === 1 ? "folder.items.one" : "folder.items.other", { n })}</>;
}

/** A PDF's page count; any other file's size. */
function FileHolds({ node }: { node: TreeNode }) {
  const { t, lang } = useI18n();
  if (node.pages) return <>{t(node.pages === 1 ? "folder.pages.one" : "folder.pages.other", { n: node.pages })}</>;
  if (node.size === null) return <>—</>;
  return <>{formatSize(node.size, lang)}</>;
}
