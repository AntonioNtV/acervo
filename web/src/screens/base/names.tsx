import type { TreeNode } from "../../api/client";
import { useErrorText } from "../../app/errors";
import { useI18n } from "../../i18n";
import { FileName } from "../../ui/FileName";
import { splitExt } from "../../ui/names";

type Named = Pick<TreeNode, "kind" | "title"> & { protected?: boolean };

/** A file's title already holds its extension; a page's never does. */
export function NodeName({ node, className }: { node: Named; className?: string }) {
  const { t } = useI18n();
  const { name: title, ext } = node.kind === "file" ? splitExt(node.title) : { name: node.title };
  const name = <FileName title={title} ext={node.kind === "page" ? "md" : ext} className={className} />;
  if (!node.protected) return name;
  return (
    <>
      {name}
      <span className="ml-1.5 shrink-0 text-11 text-text-3">{t("base.protected")}</span>
    </>
  );
}

/** A taken sibling name reads "já existe"; anything else, the generic text for its status. */
export function useTreeErrorText() {
  const { t } = useI18n();
  const errorText = useErrorText();
  return (error: unknown) => errorText(error, { title_taken: t("base.exists") });
}
