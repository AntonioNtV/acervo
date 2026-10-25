import { useRef, type KeyboardEvent } from "react";
import { useI18n } from "../i18n";
import { Button } from "./Button";
import { cx } from "./cx";
import { Icon } from "./Icon";

type View<T extends string> = { value: T; label: string };

/** The head every view of a database shares; the views are tabs the arrows move through, opening the one reached. */
export function DatabaseHeader<T extends string>({
  title,
  views,
  view,
  onView,
  onFilter,
  onSort,
  onSearch,
  onNew,
}: {
  title: string;
  views: View<T>[];
  view: T;
  onView: (view: T) => void;
  onFilter: () => void;
  onSort: () => void;
  onSearch: () => void;
  onNew: () => void;
}) {
  const { t } = useI18n();
  const tabs = useRef<HTMLDivElement>(null);

  const move = (event: KeyboardEvent) => {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    const index = (views.findIndex((v) => v.value === view) + (step ?? 0) + views.length) % views.length;
    const next = views[index];
    if (!step || !next) return;
    event.preventDefault();
    onView(next.value);
    tabs.current?.querySelectorAll<HTMLElement>('[role="tab"]')[index]?.focus();
  };

  return (
    <div className="flex flex-wrap items-center gap-4 border-b border-line pb-2.5 text-13 text-text">
      <span className="text-15 font-medium">{title}</span>
      <div
        ref={tabs}
        role="tablist"
        aria-label={t("data.views")}
        onKeyDown={move}
        className="flex min-w-0 flex-wrap gap-4"
      >
        {views.map((v) => (
          <button
            key={v.value}
            type="button"
            role="tab"
            aria-selected={v.value === view}
            tabIndex={v.value === view ? 0 : -1}
            onClick={() => onView(v.value)}
            className={cx(
              "cursor-pointer border-0 bg-transparent p-0 text-13 hover:text-text",
              v.value === view ? "font-medium text-text" : "text-text-3",
            )}
          >
            {v.label}
          </button>
        ))}
      </div>
      <div className="ml-auto flex items-center gap-0.5">
        <Button variant="quiet" size="sm" onClick={onFilter}>
          {t("data.filter")}
        </Button>
        <Button variant="quiet" size="sm" onClick={onSort}>
          {t("data.sort")}
        </Button>
        <Button variant="quiet" size="sm" icon aria-label={t("data.search")} onClick={onSearch}>
          <Icon name="search" size={14} />
        </Button>
        <Button size="sm" onClick={onNew}>
          {t("data.new")}
        </Button>
      </div>
    </div>
  );
}
