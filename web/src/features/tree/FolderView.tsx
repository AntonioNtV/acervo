import { useState } from "react";
import { Link } from "react-router-dom";
import { useChildren, type NodeDetail } from "../../api/queries";
import { useI18n } from "../../i18n";
import { cx } from "../../ui/cx";
import { folderPath, NodeName } from "./names";
import { UploadButton, useStartUpload } from "./Upload";

/** A folder opened: its children as a plain list, and where files are sent into it. */
export function FolderView({ node }: { node: NodeDetail }) {
  const { t } = useI18n();
  const children = useChildren(node.kb_id, node.id);
  const startUpload = useStartUpload(node.kb_id);
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
        startUpload(Array.from(event.dataTransfer.files), node.id);
      }}
    >
      <div className="flex items-center justify-between gap-3 text-12 text-text-3">
        <span>{folderPath(node.path)}</span>
        <UploadButton kbId={node.kb_id} parentId={node.id} />
      </div>
      <h1 className="mt-7 mb-6 text-32 font-medium tracking-[-0.035em]">{node.title}</h1>
      {children.data?.length === 0 && <p className="m-0 text-text-3">{t("tree.empty")}</p>}
      <ul className="m-0 flex list-none flex-col p-0">
        {children.data?.map((child) => (
          <li key={child.id} className="border-t border-line first:border-t-0">
            <Link
              to={`/kbs/${node.kb_id}/n/${child.id}`}
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
