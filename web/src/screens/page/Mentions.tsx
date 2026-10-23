import { Link } from "react-router-dom";
import { usePageMentions } from "../../data/pages";
import { useI18n } from "../../i18n";
import { folderPath } from "../../ui/names";
import { NodeIcon } from "../../ui/NodeIcon";

/** "Mencionada em": the pages of the base with a `[[link]]` to this one, each with the line holding it. */
export function Mentions({ nodeId }: { nodeId: string }) {
  const { t } = useI18n();
  const mentions = usePageMentions(nodeId).data ?? [];
  if (mentions.length === 0) return null;
  const n = mentions.length;
  return (
    <nav aria-label={t("page.mentions")} className="mt-10 border-t border-line pt-3">
      <span className="block pb-1 text-12 text-text-3">
        {t("page.mentions")} <span className="text-ghost">{t(n === 1 ? "page.mentions.one" : "page.mentions.other", { n })}</span>
      </span>
      <ul className="m-0 flex list-none flex-col p-0">
        {mentions.map(({ node, line }) => (
          <li key={node.id}>
            <Link
              to={`/kbs/${node.kb_id}/n/${node.id}`}
              className="-mx-1.5 flex flex-col gap-0.5 rounded-[6px] px-1.5 py-1.5 no-underline hover:bg-subtle"
            >
              <span className="flex min-w-0 items-center gap-2 text-15 text-text">
                <span className="text-text-3">
                  <NodeIcon icon={node.icon} kind="page" />
                </span>
                <span className="shrink-0 truncate">{node.title}</span>
                <span className="min-w-0 truncate text-13 text-ghost">{folderPath(node.path, node.title)}</span>
              </span>
              <span className="pl-6 text-13 leading-5 text-text-2">{line}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
