import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { NodeDetail } from "../../api/client";
import { useKbs } from "../../data/kbs";
import { useChildren } from "../../data/tree";
import { useI18n } from "../../i18n";
import { cx } from "../../ui/cx";
import { folderPath } from "../../ui/names";
import { NodeName } from "./names";
import { UploadButton, useStartUpload } from "./Upload";

/** A folder opened: its children as a plain list, and where files are sent into it. */
export function FolderView({ node }: { node: NodeDetail }) {
  return <Folder kbId={node.kb_id} folderId={node.id} title={node.title} path={folderPath(node.path, node.title)} />;
}

/** The base opened with no node chosen: its root, as a folder. */
export function BaseRootView() {
  const { kbId = "" } = useParams();
  const kb = useKbs().data?.find((summary) => summary.id === kbId);
  return <Folder kbId={kbId} folderId={null} title={kb?.name ?? ""} path="" />;
}

function Folder({ kbId, folderId, title, path }: { kbId: string; folderId: string | null; title: string; path: string }) {
  const { t } = useI18n();
  const children = useChildren(kbId, folderId);
  const startUpload = useStartUpload(kbId);
  const [over, setOver] = useState(false);
  return (
    <div
      className={cx("mx-auto min-h-full max-w-[720px] px-14 pt-10 pb-16", over && "bg-subtle")}
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
      <div className="flex items-center justify-between gap-3 text-12 text-text-3">
        <span>{path}</span>
        <UploadButton kbId={kbId} parentId={folderId} />
      </div>
      <h1 className="mt-7 mb-6 text-32 font-medium tracking-[-0.035em]">{title}</h1>
      {children.data?.length === 0 && <p className="m-0 text-text-3">{t("base.empty")}</p>}
      <ul className="m-0 flex list-none flex-col p-0">
        {children.data?.map((child) => (
          <li key={child.id} className="border-t border-line first:border-t-0">
            <Link
              to={`/kbs/${kbId}/n/${child.id}`}
              className="flex h-11 items-center text-text no-underline hover:text-text-2"
            >
              <NodeName node={child} className="truncate" />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
