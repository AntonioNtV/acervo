import { Link } from "react-router-dom";
import { useKbs } from "../../data/kbs";
import { useNode } from "../../data/tree";
import { useI18n } from "../../i18n";
import { FileName } from "../../ui/FileName";
import { NodeIcon } from "../../ui/NodeIcon";
import { splitExt } from "../../ui/names";

const linkClass = "inline-flex items-center gap-1 rounded-[4px] px-1 py-0.5 text-text-2 no-underline hover:bg-subtle";

function Sep() {
  return (
    <span aria-hidden="true" className="text-ghost">
      /
    </span>
  );
}

/** The nodes above `nodeId` and `nodeId` itself, each a link, from the base's root down. */
function Trail({ kbId, nodeId }: { kbId: string; nodeId: string }) {
  const node = useNode(nodeId).data;
  if (!node) return null;
  return (
    <>
      {node.parent_id && <Trail kbId={kbId} nodeId={node.parent_id} />}
      <Sep />
      <Link to={`/kbs/${kbId}/n/${node.id}`} className={linkClass}>
        <NodeIcon icon={node.icon} size={14} />
        {node.title}
      </Link>
    </>
  );
}

/** Base / folders and pages above / the node open, which is the only part that is not a link. */
export function Breadcrumb({ kbId, nodeId }: { kbId: string; nodeId?: string }) {
  const { t } = useI18n();
  const kb = useKbs().data?.find((summary) => summary.id === kbId);
  const node = useNode(nodeId ?? "", !!nodeId).data;
  const { name, ext } = node?.kind === "file" ? splitExt(node.title) : { name: node?.title ?? "", ext: undefined };
  return (
    <nav aria-label={t("shell.path")} className="flex min-w-0 flex-wrap items-center gap-1 text-13 text-text-2">
      {nodeId ? (
        <Link to={`/kbs/${kbId}`} className={linkClass}>
          <NodeIcon icon={kb?.icon} size={14} />
          {kb?.name}
        </Link>
      ) : (
        <span aria-current="page" className="inline-flex items-center gap-1 px-1 py-0.5 text-text">
          <NodeIcon icon={kb?.icon} size={14} />
          {kb?.name}
        </span>
      )}
      {node && (
        <>
          {node.parent_id && <Trail kbId={kbId} nodeId={node.parent_id} />}
          <Sep />
          <span aria-current="page" className="flex min-w-0 items-center gap-1 px-1 py-0.5 text-text">
            <NodeIcon icon={node.icon} size={14} />
            <FileName title={name} ext={ext} className="truncate" />
          </span>
        </>
      )}
    </nav>
  );
}
