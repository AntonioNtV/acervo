import * as RadixMenu from "@radix-ui/react-dropdown-menu";
import type { ReactNode } from "react";

/** Opens below its trigger; `align` picks which of its edges lines up with the trigger's, `width` fixes it in px. */
export function Menu({
  trigger,
  children,
  align = "start",
  width,
  label,
}: {
  trigger: ReactNode;
  children: ReactNode;
  align?: "start" | "end";
  width?: number;
  label?: string;
}) {
  return (
    <RadixMenu.Root>
      <RadixMenu.Trigger asChild>{trigger}</RadixMenu.Trigger>
      <RadixMenu.Portal>
        <RadixMenu.Content
          align={align}
          sideOffset={4}
          aria-label={label}
          style={width ? { width } : undefined}
          className="flex min-w-[180px] flex-col rounded-[8px] border border-line-2 bg-bg p-1"
        >
          {children}
        </RadixMenu.Content>
      </RadixMenu.Portal>
    </RadixMenu.Root>
  );
}

export function MenuItem({ onSelect, children }: { onSelect: () => void; children: ReactNode }) {
  return (
    <RadixMenu.Item
      onSelect={onSelect}
      className="flex h-[30px] cursor-pointer items-center rounded-[6px] px-2.5 text-13 text-text outline-none data-[highlighted]:bg-subtle data-[disabled]:text-ghost"
    >
      {children}
    </RadixMenu.Item>
  );
}

export function MenuSeparator() {
  return <RadixMenu.Separator className="my-1 h-px bg-line" />;
}
