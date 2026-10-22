import type { ReactNode } from "react";
import type { NodeDetail } from "../../api/queries";
import { useI18n } from "../../i18n";
import { FileName } from "../../ui/FileName";
import { folderPath, splitExt } from "../../ui/names";
import { DownloadLink } from "./DownloadLink";
import { FileActions } from "./FileActions";

type Props = {
  node: NodeDetail;
  /** Between the path and "arquivo original", e.g. the page count. */
  detail?: string;
  /** The viewer's own controls, before the file's actions. */
  children?: ReactNode;
};

export function FileHeader({ node, detail, children }: Props) {
  const { t } = useI18n();
  const { name, ext } = splitExt(node.title);
  const folder = folderPath(node.path, node.title);
  const subtitle = [folder, detail, t("pdf.original")].filter(Boolean).join(" · ");
  return (
    <header className="flex min-h-14 shrink-0 flex-wrap items-center justify-between gap-3 border-b border-line bg-bg py-2 pr-4 pl-5">
      <span className="flex min-w-0 flex-col">
        <h1 className="m-0 truncate text-13 font-medium">
          <FileName title={name} ext={ext} />
        </h1>
        <span className="truncate text-12 text-text-3">{subtitle}</span>
      </span>
      <span className="flex flex-wrap items-center gap-1">
        {children}
        {children && <span aria-hidden="true" className="mx-1.5 h-4 w-px bg-line-2" />}
        <FileActions node={node} />
        <DownloadLink nodeId={node.id} />
      </span>
    </header>
  );
}
