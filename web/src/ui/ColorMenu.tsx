import { useRef, type KeyboardEvent, type ReactNode } from "react";
import { useI18n } from "../i18n";
import { Icon } from "./Icon";

export type TextColor = "gray" | "brown" | "orange" | "yellow" | "green" | "blue" | "pink" | "red";

// Whole class names, so Tailwind finds them.
const COLORS: Array<[TextColor, string]> = [
  ["gray", "text-tc-gray"],
  ["brown", "text-tc-brown"],
  ["orange", "text-tc-orange"],
  ["yellow", "text-tc-yellow"],
  ["green", "text-tc-green"],
  ["blue", "text-tc-blue"],
  ["pink", "text-tc-pink"],
  ["red", "text-tc-red"],
];

/**
 * The color menu of a text selection: the eight text colors and the highlight, as a panel the caller places.
 * Picking the applied color again reports null (back to the default color); the highlight toggles.
 */
export function ColorMenu({
  color,
  highlight,
  onColor,
  onHighlight,
  onClose,
}: {
  /** null is the default color. */
  color: TextColor | null;
  highlight: boolean;
  onColor: (color: TextColor | null) => void;
  onHighlight: (highlight: boolean) => void;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const menu = useRef<HTMLDivElement>(null);
  const applied = color ? COLORS.findIndex(([c]) => c === color) : -1;

  const onKeyDown = (event: KeyboardEvent) => {
    const items = [...(menu.current?.querySelectorAll<HTMLElement>("[role=menuitemradio]") ?? [])];
    const at = items.indexOf(document.activeElement as HTMLElement);
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      items[(at + step + items.length) % items.length]?.focus();
    } else if (event.key === "Escape") {
      event.stopPropagation();
      onClose();
    } else if (event.key === "Tab") {
      onClose();
    }
  };

  const item = (key: string, on: boolean, swatch: ReactNode, label: string, pick: () => void, first: boolean) => (
    <button
      key={key}
      type="button"
      role="menuitemradio"
      aria-checked={on}
      tabIndex={first ? 0 : -1}
      autoFocus={first}
      onClick={pick}
      onMouseEnter={(event) => event.currentTarget.focus()}
      className="flex h-[30px] w-full cursor-pointer items-center gap-2.5 rounded-[6px] border-0 bg-transparent px-2.5 text-left text-13 text-text outline-none hover:bg-subtle focus:bg-subtle aria-checked:bg-subtle"
    >
      {swatch}
      {label}
      {on && (
        <span className="ml-auto inline-flex text-text-2">
          <Icon name="check" size={14} />
        </span>
      )}
    </button>
  );
  const swatch = "inline-flex size-5 flex-none items-center justify-center rounded-[4px] border border-line-2 font-medium";

  return (
    <div
      ref={menu}
      role="menu"
      aria-label={t("pickers.color.label")}
      onKeyDown={onKeyDown}
      className="w-[220px] rounded-[8px] border border-line-2 bg-bg p-1 text-13 text-text"
    >
      <div className="px-2.5 pt-1 pb-0.5 text-12 text-text-3">{t("pickers.color.text")}</div>
      {COLORS.map(([c, cls], i) =>
        item(
          c,
          c === color,
          <span aria-hidden className={`${swatch} ${cls}`}>A</span>,
          t(`pickers.color.${c}`),
          () => onColor(c === color ? null : c),
          i === Math.max(applied, 0),
        ),
      )}
      <div className="my-1 h-px bg-line" />
      <div className="px-2.5 pt-1 pb-0.5 text-12 text-text-3">{t("pickers.color.background")}</div>
      {item(
        "mark",
        highlight,
        <span aria-hidden className={`${swatch} bg-mark`}>A</span>,
        t("pickers.color.mark"),
        () => onHighlight(!highlight),
        false,
      )}
    </div>
  );
}
