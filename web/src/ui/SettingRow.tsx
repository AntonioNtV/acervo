import * as RadixMenu from "@radix-ui/react-dropdown-menu";
import { useRef } from "react";
import { Button } from "./Button";
import { Icon } from "./Icon";

/** A preference: its name and what it does, and at the right its value, which opens the options. Changes at once. */
export function SettingRow<T extends string>({
  title,
  desc,
  value,
  options,
  onChange,
}: {
  title: string;
  desc?: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  const opening = useRef(false);
  return (
    <div className="flex min-h-14 items-center justify-between gap-4 border-b border-line py-2.5">
      <span className="flex min-w-0 flex-col">
        <span className="text-13 text-text">{title}</span>
        {desc && <span className="text-12 leading-[18px] text-text-3">{desc}</span>}
      </span>
      <RadixMenu.Root onOpenChange={(open) => (opening.current = open)}>
        <RadixMenu.Trigger asChild>
          <Button variant="quiet" size="sm" aria-label={title}>
            {options.find((option) => option.value === value)?.label}
            <Icon name="caretDown" size={14} />
          </Button>
        </RadixMenu.Trigger>
        <RadixMenu.Portal>
          <RadixMenu.Content
            align="end"
            sideOffset={4}
            aria-label={title}
            // While opening, Radix focuses the menu and, from the keyboard, its first option; both go to the chosen
            // option instead, so a long list (time zones) opens where the person is. Only then: later the menu is
            // refocused as the pointer leaves an option. The max height is fixed, as Radix's is set after positioning.
            onFocus={(event) => {
              const content = event.currentTarget;
              const checked = content.querySelector<HTMLElement>('[role="menuitemradio"][data-state="checked"]');
              if (!opening.current || !checked || event.target === checked) return;
              checked.focus({ preventScroll: true });
              content.scrollTop = checked.offsetTop - (content.clientHeight - checked.offsetHeight) / 2;
              requestAnimationFrame(() => (opening.current = false));
            }}
            className="flex max-h-80 w-[200px] flex-col overflow-y-auto rounded-[8px] border border-line-2 bg-bg p-1"
          >
            <RadixMenu.RadioGroup value={value} onValueChange={(next) => onChange(next as T)}>
              {options.map((option) => (
                <RadixMenu.RadioItem
                  key={option.value}
                  value={option.value}
                  className="flex h-[30px] cursor-pointer items-center gap-2 rounded-[6px] px-2.5 text-13 text-text outline-none data-[highlighted]:bg-subtle"
                >
                  <span className="flex-1">{option.label}</span>
                  <RadixMenu.ItemIndicator className="inline-flex text-ink">
                    <Icon name="check" size={14} />
                  </RadixMenu.ItemIndicator>
                </RadixMenu.RadioItem>
              ))}
            </RadixMenu.RadioGroup>
          </RadixMenu.Content>
        </RadixMenu.Portal>
      </RadixMenu.Root>
    </div>
  );
}
