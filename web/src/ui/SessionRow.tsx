import type { ReactNode } from "react";
import { Dot } from "./Dot";

// Glyphs only this row uses, so they stay out of Icon's set.
const GLYPHS = {
  desktop: <path d="M3 5h18v11H3zM8 20h8M12 16v4" />,
  phone: <path d="M7 3h10v18H7zM11 18h2" />,
};

/**
 * A browser with the account open: `device` ("Chrome no macOS") and `when` under it; at the right `action` (Encerrar),
 * or for this browser's own session, `current` ("Este aparelho") with a green dot.
 */
export function SessionRow({
  device,
  when,
  phone = false,
  current,
  action,
}: {
  device: string;
  when: string;
  phone?: boolean;
  current?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex min-h-14 items-center gap-3 border-b border-line px-2 py-2.5 text-13">
      <svg
        viewBox="0 0 24 24"
        width={16}
        height={16}
        aria-hidden="true"
        className="shrink-0 fill-none stroke-current stroke-[1.5] text-text-3"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {GLYPHS[phone ? "phone" : "desktop"]}
      </svg>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-text">{device}</span>
        <span className="truncate text-12 leading-[18px] text-text-3">{when}</span>
      </span>
      {current ? <Dot tone="ok">{current}</Dot> : action}
    </div>
  );
}
