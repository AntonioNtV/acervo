import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { NodeDetail } from "../../api/client";
import { useFileVersions } from "../../data/files";
import { useKbs } from "../../data/kbs";
import { useNode } from "../../data/tree";
import { locale, useI18n } from "../../i18n";
import { TopBar } from "../shell/TopBar";
import { DownloadLink } from "./DownloadLink";
import { FileMenu } from "./FileActions";
import { formatSize } from "./format";

type Props = {
  node: NodeDetail;
  /** After "arquivo original", e.g. the page count. */
  detail?: string;
  /** The viewer's own controls, before "Baixar". */
  children?: ReactNode;
};

/** The top bar over a file (the viewer's controls, "Baixar", ⋯) and the line that says what the file is. */
export function FileHeader({ node, detail, children }: Props) {
  const { t, lang } = useI18n();
  const versions = node.versions;
  const what = [t("file.original"), detail, node.file && formatSize(node.file.size, lang)].filter(Boolean).join(" · ");
  return (
    <div className="shrink-0 bg-bg">
      <TopBar
        kbId={node.kb_id}
        nodeId={node.id}
        actions={
          <>
            {children}
            {children && <span aria-hidden="true" className="mx-1 h-4 w-px bg-line-2" />}
            <DownloadLink nodeId={node.id} filename={node.title} />
          </>
        }
        menu={<FileMenu node={node} />}
      />
      <p className="m-0 flex flex-wrap gap-x-4 px-[22px] pt-1.5 pb-3.5 text-12 text-text-3">
        <span>{what}</span>
        {versions > 0 && (
          <span>
            {t(versions === 1 ? "file.versions.one" : "file.versions.other", { n: versions })}
            {versions > 1 && <Replaced nodeId={node.id} />}
          </span>
        )}
        <span>
          {t("file.inside")} <Parent kbId={node.kb_id} parentId={node.parent_id} />
        </span>
      </p>
    </div>
  );
}

/** " · substituído em 22 de out.": when the newest older content was set aside. */
function Replaced({ nodeId }: { nodeId: string }) {
  const { t, lang } = useI18n();
  const newest = useFileVersions(nodeId).data?.[0];
  if (!newest) return null;
  const date = new Date(newest.replaced_at).toLocaleDateString(locale(lang), { day: "numeric", month: "short" });
  return <> · {t("file.replaced", { date })}</>;
}

/** The folder or page that holds the file, or the base when it sits at the root. */
function Parent({ kbId, parentId }: { kbId: string; parentId: string | null }) {
  const kb = useKbs().data?.find((summary) => summary.id === kbId);
  const parent = useNode(parentId ?? "", !!parentId).data;
  const name = parentId ? parent?.title : kb?.name;
  return (
    <Link to={parentId ? `/kbs/${kbId}/n/${parentId}` : `/kbs/${kbId}`} className="text-text-2 hover:text-text">
      {name}
    </Link>
  );
}
