import { forwardRef, type InputHTMLAttributes } from "react";
import { cx } from "./cx";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...rest },
  ref,
) {
  return (
    <input
      ref={ref}
      className={cx(
        "h-[30px] w-full rounded-[7px] border border-line-2 bg-bg px-2.5 text-13 text-text placeholder:text-ghost",
        "focus:border-ink focus:shadow-[0_0_0_3px_var(--accent-soft)] focus:outline-none focus-visible:outline-none",
        "aria-invalid:border-err disabled:cursor-default disabled:opacity-50",
        className,
      )}
      {...rest}
    />
  );
});
