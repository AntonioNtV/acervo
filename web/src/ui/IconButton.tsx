import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cx } from "./cx";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { "aria-label": string; size?: "md" | "sm" };

/** A square, borderless button holding one icon; its name is its `aria-label`. */
export const IconButton = forwardRef<HTMLButtonElement, Props>(function IconButton(
  { size = "md", type = "button", className, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cx(
        "inline-flex shrink-0 cursor-pointer items-center justify-center rounded-[6px] border-0 bg-transparent p-0 text-text-2",
        "enabled:hover:bg-subtle enabled:hover:text-text aria-pressed:bg-subtle aria-pressed:text-text",
        "disabled:cursor-default disabled:opacity-50",
        size === "sm" ? "size-[22px]" : "size-7",
        className,
      )}
      {...rest}
    />
  );
});
