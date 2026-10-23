import { useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import type { NodeDetail, TreeNode } from "../../api/client";
import { useErrorText } from "../../app/errors";
import { useFavorite } from "../../data/favorites";
import { useKbs } from "../../data/kbs";
import { useChildren, useDescribeNode, useRenameNode } from "../../data/tree";
import { useI18n } from "../../i18n";
import { cx } from "../../ui/cx";
import { Icon } from "../../ui/Icon";
import { IconButton } from "../../ui/IconButton";
import { Menu, MenuItem } from "../../ui/Menu";
import { NodeIcon } from "../../ui/NodeIcon";
import { NodeName, useCreateUntitledPage, useTreeErrorText } from "../base/names";
import { FileDropZone, UploadGlyph, useStartUpload } from "../base/Upload";
import { formatSize } from "../file/format";
import { Cover, HeaderDecor } from "../page/Cover";
import { TopBar } from "../shell/TopBar";

/** A folder opened, as a page: its title, its description, its children as links, and how to add to it. */
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
  const untitled = useCreateUntitledPage(kbId, folderId);
  const errorText = useTreeErrorText();
  const startUpload = useStartUpload(kbId);
  const input = useRef<HTMLInputElement>(null);

  const all = children.data ?? [];

  function newPage() {
    untitled.create().then(
      (page) => navigate(`/kbs/${kbId}/n/${page.id}`),
      () => undefined,
    );
  }

  return (
    <>
      <TopBar kbId={kbId} nodeId={folderId ?? undefined} menu={folder && <FolderMenu folder={folder} />} />
      {folder && <Cover node={folder} />}
      <FileDropZone
        kbId={kbId}
        parentId={folderId}
        name={title}
        className="mx-auto box-border min-h-[calc(100%-44px)] w-full max-w-[720px] px-8 pt-10 pb-30"
      >
        <div className="group/header">
          {folder && <HeaderDecor node={folder} />}
          {folder ? <Title node={folder} /> : <h1 className={titleClass}>{title}</h1>}
          {folder ? (
            <Description node={folder} />
          ) : (
            description && <p className="m-0 mt-1.5 text-15 leading-6 text-text-2">{description}</p>
          )}
        </div>

        <ul className="m-0 mt-6 flex list-none flex-col p-0">
          {all.map((child) => (
            <li key={child.id}>
              <Row kbId={kbId} node={child} />
            </li>
          ))}
        </ul>
        {children.isSuccess && all.length === 0 && <p className="m-0 mt-6 text-15 text-ghost">{t("folder.empty")}</p>}

        <div className="mt-3 -ml-1.5 flex flex-wrap gap-1">
          <button type="button" disabled={untitled.isPending} onClick={newPage} className={quietClass}>
            <Icon name="plus" size={14} />
            {t("folder.new.page")}
          </button>
          <button type="button" onClick={() => input.current?.click()} className={quietClass}>
            <UploadGlyph />
            {t("folder.upload")}
          </button>
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
        </div>
        {untitled.error && <p className="m-0 mt-1 text-12 text-err">{errorText(untitled.error)}</p>}
      </FileDropZone>
    </>
  );
}

/** The folder's ⋯: in or out of the favorites. */
function FolderMenu({ folder }: { folder: NodeDetail }) {
  const { t } = useI18n();
  const favorite = useFavorite();
  const errorText = useErrorText();
  return (
    <>
      {favorite.isError && <span className="px-1 text-12 text-err">{errorText(favorite.error)}</span>}
      <Menu
        trigger={
          <IconButton aria-label={t("folder.more")}>
            <Icon name="more" />
          </IconButton>
        }
      >
        <MenuItem onSelect={() => favorite.mutate({ nodeId: folder.id, favorite: !folder.favorite })}>
          {t(folder.favorite ? "shell.favorite.remove" : "shell.favorite.add")}
        </MenuItem>
      </Menu>
    </>
  );
}

const quietClass =
  "flex h-7 cursor-pointer items-center gap-1.5 rounded-[6px] border-0 bg-transparent px-1.5 font-[inherit] text-13 text-text-3 hover:bg-subtle hover:text-text disabled:cursor-default";

const titleClass = "m-0 text-32 leading-[40px] font-medium tracking-[-0.025em] break-words";

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
          "mt-1.5 block cursor-text border-0 bg-transparent p-0 text-left font-[inherit] leading-6",
          // An empty description is only a hint, shown when the header is hovered or focused, as Notion does.
          node.description
            ? "text-15 text-text-2"
            : "text-13 text-ghost opacity-0 group-hover/header:opacity-100 focus-visible:opacity-100",
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
  return (
    <Link
      to={`/kbs/${kbId}/n/${node.id}`}
      className="group -mx-1.5 flex min-h-9 items-center gap-2 rounded-[6px] px-1.5 text-15 text-text no-underline hover:bg-subtle"
    >
      <span className="text-text-3">
        <NodeIcon icon={node.icon} kind={node.kind} />
      </span>
      <NodeName node={node} pageExt={false} className="min-w-0 truncate" />
      <span className="ml-auto pl-4 text-13 whitespace-nowrap text-ghost">
        {node.kind === "file" ? <FileHolds node={node} /> : <Holds node={node} />}
      </span>
    </Link>
  );
}

/** How many live things a folder or page holds, or a dash. */
function Holds({ node }: { node: TreeNode }) {
  const { t } = useI18n();
  const n = node.child_count;
  if (!n) return null;
  return <>{t(n === 1 ? "folder.items.one" : "folder.items.other", { n })}</>;
}

/** A PDF's page count; any other file's size. */
function FileHolds({ node }: { node: TreeNode }) {
  const { t, lang } = useI18n();
  if (node.pages) return <>{t(node.pages === 1 ? "folder.pages.one" : "folder.pages.other", { n: node.pages })}</>;
  if (node.size === null) return null;
  return <>{formatSize(node.size, lang)}</>;
}
