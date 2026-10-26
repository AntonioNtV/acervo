import * as RadixMenu from "@radix-ui/react-dropdown-menu";
import type { Tone } from "./Dot";
import { Icon } from "./Icon";
import { StatusValue } from "./StatusValue";

export type SelectOption = { value: string; label: string; tone?: Tone };

/** A 30 px field that opens its options below, as wide as itself; an option with a `tone` shows as a StatusValue. */
export function SelectField({
  label,
  value,
  options,
  onChange,
  width = 200,
  disabled,
}: {
  label: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  /** In px, or "100%" in a form. */
  width?: number | string;
  disabled?: boolean;
}) {
  const chosen = options.find((option) => option.value === value);
  return (
    <RadixMenu.Root>
      <RadixMenu.Trigger
        aria-label={label}
        disabled={disabled}
        style={{ width }}
        className="flex h-[30px] max-w-full cursor-pointer items-center justify-between gap-2 rounded-[7px] border border-line-2 bg-bg px-2.5 text-left text-13 text-text disabled:cursor-default disabled:opacity-50 data-[state=open]:border-ink data-[state=open]:shadow-[0_0_0_3px_var(--accent-soft)]"
      >
        {chosen && <Shown option={chosen} />}
        <Icon name="caretDown" size={14} className="text-text-3" />
      </RadixMenu.Trigger>
      <RadixMenu.Portal>
        <RadixMenu.Content
          align="start"
          sideOffset={4}
          aria-label={label}
          className="flex w-[var(--radix-dropdown-menu-trigger-width)] flex-col rounded-[8px] border border-line-2 bg-bg p-1.5"
        >
          <RadixMenu.RadioGroup value={value} onValueChange={onChange}>
            {options.map((option) => (
              <RadixMenu.RadioItem
                key={option.value}
                value={option.value}
                className="flex h-[30px] cursor-pointer items-center gap-2 rounded-[6px] px-2 text-13 text-text outline-none data-[highlighted]:bg-subtle"
              >
                <Shown option={option} />
                <RadixMenu.ItemIndicator className="ml-auto inline-flex text-ink">
                  <Icon name="check" size={14} />
                </RadixMenu.ItemIndicator>
              </RadixMenu.RadioItem>
            ))}
          </RadixMenu.RadioGroup>
        </RadixMenu.Content>
      </RadixMenu.Portal>
    </RadixMenu.Root>
  );
}

function Shown({ option }: { option: SelectOption }) {
  return option.tone ? <StatusValue label={option.label} tone={option.tone} /> : <span>{option.label}</span>;
}
