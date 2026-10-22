import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cx } from "./cx";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "ink" | "quiet";
  size?: "md" | "sm";
  icon?: boolean;
};

const variants = {
  default: "border-line-2 bg-bg text-text enabled:hover:bg-subtle",
  ink: "border-ink bg-ink text-on-ink",
  quiet: "border-transparent bg-transparent text-text-2 enabled:hover:bg-subtle enabled:hover:text-text",
};

const sizes = {
  md: "h-[30px] rounded-[7px] text-13",
  sm: "h-[26px] rounded-[6px] text-12",
};

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = "default", size = "md", icon = false, type = "button", className, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cx(
        "inline-flex shrink-0 cursor-pointer items-center justify-center gap-1.5 border font-medium whitespace-nowrap",
        "disabled:cursor-default disabled:opacity-50",
        variants[variant],
        sizes[size],
        icon ? (size === "sm" ? "w-[26px]" : "w-[30px]") : size === "sm" ? "px-2" : "px-3",
        className,
      )}
      {...rest}
    />
  );
});
