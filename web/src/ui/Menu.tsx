import * as RadixMenu from "@radix-ui/react-dropdown-menu";
import type { ReactNode } from "react";

export function Menu({ trigger, children }: { trigger: ReactNode; children: ReactNode }) {
  return (
    <RadixMenu.Root>
      <RadixMenu.Trigger asChild>{trigger}</RadixMenu.Trigger>
      <RadixMenu.Portal>
        <RadixMenu.Content
          align="start"
          sideOffset={4}
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
