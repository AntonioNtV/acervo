import { useI18n } from "../i18n";
import type { Tone } from "./Dot";
import { Input } from "./Input";
import { Menu, MenuItem } from "./Menu";
import { StatusValue } from "./StatusValue";

export type PropertyType = "select" | "text" | "number" | "date";

const TYPES: PropertyType[] = ["select", "text", "number", "date"];

/**
 * The panel that edits a property of a database: its name, its type and, for a select, its options. The caller places
 * it, as it does EmojiPicker; Escape closes it.
 */
export function PropertyEditor({
  name,
  type,
  options,
  onChange,
  onAddOption,
  onClose,
}: {
  name: string;
  type: PropertyType;
  /** The options of a select; shown only when `type` is "select". */
  options: Array<{ label: string; tone: Tone }>;
  onChange: (property: { name: string; type: PropertyType }) => void;
  onAddOption: () => void;
  onClose: () => void;
}) {
  const { t } = useI18n();

  return (
    <div
      role="dialog"
      aria-label={name}
      onKeyDown={(event) => {
        // The type menu sits in a portal and closes itself on Escape; that one must not close the editor too.
        if (event.key === "Escape" && event.currentTarget.contains(event.target as Node)) {
          event.stopPropagation();
          onClose();
        }
      }}
      className="flex w-[240px] flex-col rounded-[8px] border border-line-2 bg-bg p-1.5 text-13 text-text"
    >
      <div className="flex flex-col gap-0.5 px-2 pt-1 pb-1.5">
        <Input
          aria-label={t("data.property.name")}
          value={name}
          onChange={(event) => onChange({ name: event.target.value, type })}
          className="font-medium"
        />
        <Menu
          trigger={
            <button
              type="button"
              className="cursor-pointer self-start border-0 bg-transparent p-0 text-12 text-text-3 hover:text-text"
            >
              {t("data.property.type", { type: t(`data.type.${type}`) })}
            </button>
          }
        >
          {TYPES.map((option) => (
            <MenuItem key={option} onSelect={() => onChange({ name, type: option })}>
              {t(`data.type.${option}`)}
            </MenuItem>
          ))}
        </Menu>
      </div>
      {type === "select" && (
        <>
          {options.map((option) => (
            <div key={option.label} className="flex h-[30px] items-center rounded-[6px] px-2 hover:bg-subtle">
              <StatusValue label={option.label} tone={option.tone} />
            </div>
          ))}
          <div className="-mx-1.5 my-1 h-px bg-line" />
          <button
            type="button"
            onClick={onAddOption}
            className="flex h-[30px] cursor-pointer items-center rounded-[6px] border-0 bg-transparent px-2 text-13 text-text-3 hover:bg-subtle"
          >
            {t("data.option.new")}
          </button>
        </>
      )}
    </div>
  );
}
