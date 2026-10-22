import { ApiError, type TreeNode } from "../../api/queries";
import { useI18n } from "../../i18n";
import { FileName } from "../../ui/FileName";

type Named = Pick<TreeNode, "kind" | "title"> & { protected?: boolean };

/** A file's title already holds its extension; a page's never does. */
export function NodeName({ node, className }: { node: Named; className?: string }) {
  const { t } = useI18n();
  const dot = node.title.lastIndexOf(".");
  const name =
    node.kind === "page" ? (
      <FileName title={node.title} ext="md" className={className} />
    ) : node.kind === "file" && dot > 0 ? (
      <FileName title={node.title.slice(0, dot)} ext={node.title.slice(dot + 1)} className={className} />
    ) : (
      <FileName title={node.title} className={className} />
    );
  if (!node.protected) return name;
  return (
    <>
      {name}
      <span className="ml-1.5 shrink-0 text-11 text-text-3">{t("tree.protected")}</span>
    </>
  );
}

/** The folders above a node, from the `path` the API gives (which ends in the node itself). */
export function folderPath(path: string): string {
  return path.split("/").slice(0, -1).join(" / ");
}

/** A taken sibling name reads "já existe"; anything else says what the API said. */
export function useErrorText() {
  const { t } = useI18n();
  return (error: unknown) =>
    error instanceof ApiError && error.status === 409 ? t("tree.exists") : (error as Error).message;
}
