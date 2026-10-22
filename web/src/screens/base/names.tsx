import type { TreeNode } from "../../api/client";
import { useErrorText } from "../../app/errors";
import { normalizeLinkTarget } from "../../data/pages";
import { ApiError } from "../../data/request";
import { useChildren, useCreateNode } from "../../data/tree";
import { useI18n } from "../../i18n";
import { FileName } from "../../ui/FileName";
import { splitExt } from "../../ui/names";

type Named = Pick<TreeNode, "kind" | "title"> & { protected?: boolean };

/**
 * A file's title already holds its extension; a page's never does. Where an icon already tells a page apart (the
 * sidebar), `pageExt` drops its `.md`.
 */
export function NodeName({ node, className, pageExt = true }: { node: Named; className?: string; pageExt?: boolean }) {
  const { t } = useI18n();
  const { name: title, ext } = node.kind === "file" ? splitExt(node.title) : { name: node.title };
  const name = <FileName title={title} ext={node.kind === "page" ? (pageExt ? "md" : undefined) : ext} className={className} />;
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

/**
 * Creates a page under `parentId` named "Sem título", "Sem título 2", …: the first name no sibling page has, and the
 * next one when the API says it was taken meanwhile. Rejects on any other failure, which `error` holds to be shown.
 */
export function useCreateUntitledPage(kbId: string, parentId: string | null) {
  const { t } = useI18n();
  const siblings = useChildren(kbId, parentId).data ?? [];
  const { mutateAsync, isPending, error } = useCreateNode(kbId);

  const create = async () => {
    const taken = new Set(siblings.filter((child) => child.kind === "page").map((page) => normalizeLinkTarget(page.title)));
    const base = t("page.untitled");
    for (let n = 1; ; n++) {
      const title = n === 1 ? base : `${base} ${n}`;
      if (taken.has(normalizeLinkTarget(title))) continue;
      try {
        return await mutateAsync({ kind: "page", parent_id: parentId, title });
      } catch (failure) {
        if (!(failure instanceof ApiError && failure.code === "title_taken")) throw failure;
      }
    }
  };

  return { create, isPending, error };
}
