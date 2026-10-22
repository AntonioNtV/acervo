import * as RadixDialog from "@radix-ui/react-dialog";
import type { ReactNode } from "react";

type Props = {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  trigger?: ReactNode;
  title: string;
  description?: string;
  children?: ReactNode;
  footer?: ReactNode;
};

export function Dialog({ open, onOpenChange, trigger, title, description, children, footer }: Props) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      {trigger && <RadixDialog.Trigger asChild>{trigger}</RadixDialog.Trigger>}
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 bg-[color-mix(in_srgb,var(--text)_24%,transparent)]" />
        <RadixDialog.Content
          {...(description ? {} : { "aria-describedby": undefined })}
          className="fixed top-1/2 left-1/2 flex w-[min(440px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 flex-col gap-4 rounded-[10px] border border-line-2 bg-bg p-5"
        >
          <div className="flex flex-col gap-1">
            <RadixDialog.Title className="m-0 text-15 font-medium tracking-[-0.01em]">{title}</RadixDialog.Title>
            {description && (
              <RadixDialog.Description className="m-0 text-text-3">{description}</RadixDialog.Description>
            )}
          </div>
          {children}
          {footer && <div className="flex justify-end gap-1.5">{footer}</div>}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}

export const DialogClose = RadixDialog.Close;
