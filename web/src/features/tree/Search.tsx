import { Link } from "react-router-dom";
import { useSearch } from "../../api/queries";
import { useI18n } from "../../i18n";
import { folderPath } from "../../ui/names";
import { NodeName } from "./names";

/** Name search inside a base; opening a result hands it to the tree, which expands down to it. */
export function SearchResults({ kbId, q, onOpen }: { kbId: string; q: string; onOpen: () => void }) {
  const { t } = useI18n();
  const search = useSearch(kbId, q);
  if (!search.data) return null;
  if (search.data.length === 0) return <p className="m-0 px-2.5 py-1 text-12 text-text-3">{t("tree.search.none")}</p>;
  return (
    <ul aria-label={t("tree.search")} className="m-0 flex list-none flex-col gap-px p-0">
      {search.data.map((hit) => (
        <li key={hit.id}>
          <Link
            to={`/kbs/${kbId}/n/${hit.id}`}
            onClick={onOpen}
            className="flex flex-col rounded-[6px] px-2.5 py-1 text-text-2 no-underline hover:bg-subtle hover:text-text"
          >
            <NodeName node={hit} className="truncate" />
            {hit.path !== hit.title && (
              <span className="truncate text-12 text-text-3">{folderPath(hit.path, hit.title)}</span>
            )}
          </Link>
        </li>
      ))}
    </ul>
  );
}
