import type { ReactNode } from "react";

/** The strokes of the canvas's icons; each is a 24-unit path drawn in the current color. */
const paths = {
  page: (
    <>
      <path d="M7 3h7l4 4v14H7z" />
      <path d="M14 3v4h4M10 12h5M10 16h5" />
    </>
  ),
  file: (
    <>
      <path d="M7 3h7l4 4v14H7z" />
      <path d="M14 3v4h4" />
    </>
  ),
  folder: <path d="M3 7h6l2 2h10v10H3z" />,
  bases: <path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" />,
  search: (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m20 20-4.2-4.2" />
    </>
  ),
  recent: (
    <>
      <path d="M12 7v5l3 2" />
      <circle cx="12" cy="12" r="8" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  trash: <path d="M5 7h14M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />,
  more: (
    <>
      <circle cx="5" cy="12" r=".9" />
      <circle cx="12" cy="12" r=".9" />
      <circle cx="19" cy="12" r=".9" />
    </>
  ),
  close: <path d="M18 6 6 18M6 6l12 12" />,
  collapse: <path d="m11 17-5-5 5-5M18 17l-5-5 5-5" />,
  expand: <path d="m13 17 5-5-5-5M6 17l5-5-5-5" />,
  caretRight: <path d="m10 7 5 5-5 5" />,
  caretDown: <path d="m7 10 5 5 5-5" />,
  chevronLeft: <path d="m15 6-6 6 6 6" />,
  chevronRight: <path d="m9 6 6 6-6 6" />,
  upload: <path d="M12 16V4M6 10l6-6 6 6M5 20h14" />,
  download: <path d="M12 4v12M6 10l6 6 6-6M5 20h14" />,
  minus: <path d="M6 12h12" />,
  check: <path d="m5 12 5 5 9-10" />,
  star: <path d="m12 4 2.4 5 5.4.6-4 3.7 1.1 5.3L12 16l-4.9 2.6 1.1-5.3-4-3.7 5.4-.6z" />,
  image: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="1.5" />
      <path d="m3 16 5-5 4 4 3-3 6 6" />
    </>
  ),
  link: (
    <path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" />
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v5M12 16h.01" />
    </>
  ),
  play: <path d="m10 7 5 5-5 5" />,
  pause: <path d="M9 6v12M15 6v12" />,
  attach: <path d="m21 11-8.5 8.5a5 5 0 0 1-7-7L14 4a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L15 7" />,
  send: <path d="M12 19V5M5 12l7-7 7 7" />,
} satisfies Record<string, ReactNode>;

export type IconName = keyof typeof paths;

export function Icon({ name, size = 16, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      aria-hidden="true"
      className={`shrink-0 fill-none stroke-current stroke-[1.5] ${className ?? ""}`}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name]}
    </svg>
  );
}
