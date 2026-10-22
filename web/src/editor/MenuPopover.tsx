import { useI18n } from "../i18n";
import { cx } from "../ui/cx";
import { Icon } from "./icons";

export type MenuItem = { key: string; icon: string; title: string; hint?: string; shortcut?: string; group: string };

/** The "/" menu and the page picker: options grouped under small labels, chosen by arrows and Enter or a click. */
export function MenuPopover({
  items,
  active,
  rect,
  onPick,
  onHover,
}: {
  items: MenuItem[];
  active: number;
  rect: DOMRect | null;
  onPick: (index: number) => void;
  onHover: (index: number) => void;
}) {
  const { t } = useI18n();
  const style = rect ? { left: rect.left, top: rect.bottom + 6 } : { left: 0, top: 0 };
  return (
    <div
      role="listbox"
      aria-label={t("editor.menu.label")}
      style={style}
      className="fixed z-30 flex max-h-[360px] w-[320px] flex-col overflow-y-auto rounded-[8px] border border-line-2 bg-bg p-1.5"
      // Keeps the editor's selection, so the chosen item applies where "/" was typed.
      onMouseDown={(event) => event.preventDefault()}
    >
      {items.length === 0 && <p className="m-0 px-2 py-1.5 text-13 text-text-3">{t("editor.menu.empty")}</p>}
      {items.map((item, index) => (
        <div key={item.key}>
          {item.group !== items[index - 1]?.group && (
            <div className="px-2 pt-1.5 pb-1 text-12 text-text-3">{item.group}</div>
          )}
          <button
            type="button"
            role="option"
            aria-selected={index === active}
            onClick={() => onPick(index)}
            onMouseEnter={() => onHover(index)}
            className={cx(
              "flex w-full cursor-pointer items-center gap-2.5 rounded-[6px] border-0 px-1.5 py-[5px] text-left text-text",
              index === active ? "bg-subtle" : "bg-transparent",
            )}
          >
            <span className="inline-flex h-10 w-10 flex-none items-center justify-center rounded-[6px] border border-line-2 bg-bg text-text-2">
              <Icon name={item.icon} />
            </span>
            <span className="flex min-w-0 flex-col">
              <span className="truncate text-[14px] leading-5">{item.title}</span>
              {item.hint && <span className="text-12 leading-4 text-text-3">{item.hint}</span>}
            </span>
            {item.shortcut && <span className="ml-auto pr-1 text-12 text-ghost">{item.shortcut}</span>}
          </button>
        </div>
      ))}
      <div className="-mx-1.5 mt-1.5 flex justify-between border-t border-line px-2.5 pt-1.5 pb-0.5 text-12 text-text-3">
        <span>{t("editor.menu.keys")}</span>
        <span>{t("editor.menu.close")}</span>
      </div>
    </div>
  );
}
