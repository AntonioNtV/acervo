import { useState, type DragEvent } from "react";
import { NavLink } from "react-router-dom";
import { useFavorite, useFavorites } from "../../data/favorites";
import { useKbs } from "../../data/kbs";
import { useI18n } from "../../i18n";
import { cx } from "../../ui/cx";
import { NodeIcon } from "../../ui/NodeIcon";

const FAVORITE_TYPE = "application/x-acervo-favorite";

type Drop = { id: string; after: boolean };

/**
 * "Favoritos" on top of the sidebar, across the current organization's bases, in the person's order; dragging one puts
 * it where it is dropped.
 */
export function Favorites() {
  const { t } = useI18n();
  const kbs = useKbs().data;
  const favorites = (useFavorites().data ?? []).filter((favorite) => kbs?.some((kb) => kb.id === favorite.kb_id));
  const place = useFavorite();
  const [drop, setDrop] = useState<Drop | null>(null);

  if (favorites.length === 0) return null;

  const dropOf = (event: DragEvent<HTMLElement>, id: string): Drop => {
    const box = event.currentTarget.getBoundingClientRect();
    return { id, after: event.clientY - box.top > box.height / 2 };
  };

  const onDrop = (event: DragEvent<HTMLElement>, index: number) => {
    event.preventDefault();
    const target = dropOf(event, favorites[index]!.id);
    setDrop(null);
    const nodeId = event.dataTransfer.getData(FAVORITE_TYPE);
    const beforeId = target.after ? (favorites[index + 1]?.id ?? null) : target.id;
    if (!nodeId || nodeId === beforeId) return;
    place.mutate({ nodeId, favorite: true, before_id: beforeId });
  };

  return (
    <section aria-label={t("shell.favorites")} className="mt-3 flex flex-col gap-px">
      <span className="flex h-[26px] items-center px-2 text-12 font-medium text-text-3">{t("shell.favorites")}</span>
      <ul className="m-0 flex list-none flex-col gap-px p-0">
        {favorites.map((favorite, index) => (
          <li
            key={favorite.id}
            draggable
            onDragStart={(event) => {
              event.dataTransfer.setData(FAVORITE_TYPE, favorite.id);
              event.dataTransfer.effectAllowed = "move";
            }}
            onDragOver={(event) => {
              event.preventDefault();
              setDrop(dropOf(event, favorite.id));
            }}
            onDragLeave={() => setDrop(null)}
            onDrop={(event) => onDrop(event, index)}
            className={cx(
              "rounded-[6px]",
              drop?.id === favorite.id &&
                (drop.after ? "shadow-[inset_0_-1px_0_var(--text-3)]" : "shadow-[inset_0_1px_0_var(--text-3)]"),
            )}
          >
            <NavLink
              to={`/kbs/${favorite.kb_id}/n/${favorite.id}`}
              className={({ isActive }) =>
                cx(
                  "flex h-7 min-w-0 items-center gap-1.5 rounded-[6px] px-2 text-13 text-text-2 no-underline hover:bg-muted",
                  isActive && "bg-muted font-medium text-text",
                )
              }
            >
              <NodeIcon icon={favorite.icon} kind={favorite.kind} size={14} />
              <span className="min-w-0 truncate">{favorite.title}</span>
              <span className="min-w-0 shrink-[2] truncate text-12 font-normal text-ghost">
                {kbs?.find((kb) => kb.id === favorite.kb_id)?.name}
              </span>
            </NavLink>
          </li>
        ))}
      </ul>
    </section>
  );
}
