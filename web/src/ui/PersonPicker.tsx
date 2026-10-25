import { useEffect, useRef, useState } from "react";
import { useI18n } from "../i18n";
import { cx } from "./cx";

export type Person = { id: string; name: string; email: string };

function initials(name: string): string {
  const words = name.trim().split(/\s+/);
  return ((words[0]?.[0] ?? "") + (words.length > 1 ? (words.at(-1)?.[0] ?? "") : "")).toUpperCase();
}

/**
 * The people matching what follows an "@", as a panel the caller places. Focus stays where the person types, so the
 * panel takes ↑ ↓ Enter and Escape from the whole document while it is open.
 */
export function PersonPicker({
  query,
  people,
  onPick,
  onClose,
}: {
  query: string;
  people: Person[];
  onPick: (person: Person) => void;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const [highlighted, setHighlighted] = useState(0);
  const active = Math.min(highlighted, Math.max(people.length - 1, 0));
  const latest = useRef({ people, active, onPick, onClose });
  latest.current = { people, active, onPick, onClose };

  useEffect(() => setHighlighted(0), [query]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const { people, active, onPick, onClose } = latest.current;
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        if (!people.length) return;
        const step = event.key === "ArrowDown" ? 1 : -1;
        setHighlighted((active + step + people.length) % people.length);
      } else if (event.key === "Enter" && people[active]) {
        onPick(people[active]);
      } else if (event.key === "Escape") {
        onClose();
      } else {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
    };
    // Capture, so the editor under the panel never sees the keys the panel uses.
    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, []);

  return (
    <div
      role="listbox"
      aria-label={t("pickers.person.label", { query })}
      // Keeps the focus and selection where the person types.
      onMouseDown={(event) => event.preventDefault()}
      className="w-[300px] max-w-full rounded-[8px] border border-line-2 bg-bg p-1 text-13 text-text"
    >
      {people.length === 0 ? (
        <p className="m-0 px-2 py-1 text-text-3">{t("pickers.person.none")}</p>
      ) : (
        people.map((person, index) => (
          <div
            key={person.id}
            role="option"
            aria-selected={index === active}
            onClick={() => onPick(person)}
            onMouseEnter={() => setHighlighted(index)}
            className={cx(
              "flex min-h-7 cursor-pointer items-center gap-2 rounded-[6px] px-2",
              index === active && "bg-subtle",
            )}
          >
            <span className="size-5 flex-none rounded-full bg-muted text-center text-[10px] leading-5 font-medium text-text-2">
              {initials(person.name)}
            </span>
            <span className="truncate">{person.name}</span>
            <span className="ml-auto truncate text-12 text-text-3">{person.email}</span>
          </div>
        ))
      )}
    </div>
  );
}
