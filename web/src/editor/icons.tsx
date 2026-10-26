const PATHS: Record<string, string> = {
  text: "M6 6h12M12 6v12",
  h1: "M5 6v12M13 6v12M5 12h8M17 10l2-1v9",
  h2: "M4 6v12M12 6v12M4 12h8M16 10a2 2 0 1 1 4 1l-4 7h4",
  h3: "M4 6v12M12 6v12M4 12h8M16 9h4l-2 3a2 2 0 1 1-2 3",
  h4: "M4 6v12M12 6v12M4 12h8M19 18V9l-4 6h5",
  h5: "M4 6v12M12 6v12M4 12h8M20 9h-4v3.5h1.5a2.25 2.25 0 1 1 0 4.5H16",
  h6: "M4 6v12M12 6v12M4 12h8M19.5 9H18a2 2 0 0 0-2 2v4.75a2.25 2.25 0 1 0 2.25-2.25H16",
  toggleHeading: "m3 9 3 3-3 3M10 6v12M18 6v12M10 12h8",
  bullet: "M9 7h11M9 12h11M9 17h11M4.5 7h.01M4.5 12h.01M4.5 17h.01",
  numbered: "M10 7h10M10 12h10M10 17h10M4 6l1.5-1v4M4 15h2.5L4 19h2.5",
  todo: "M4 5h5v5H4zM5.5 7.5l1 1 2-2M12 7.5h8M4 14h5v5H4zM12 16.5h8",
  quote: "M5 5v14M10 8h9M10 12h9M10 16h6",
  callout: "M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM12 8v5M12 16h.01",
  toggle: "m9 6 6 6-6 6",
  code: "m9 8-4 4 4 4M15 8l4 4-4 4",
  table: "M4 5h16v14H4zM4 10h16M4 14.5h16M10 5v14",
  divider: "M4 12h16",
  subpage: "M7 3h7l4 4v14H7zM14 3v4h4",
  columns: "M4 5h16v14H4zM12 5v14",
  toc: "M4 6h.01M8 6h12M7 12h.01M11 12h9M7 18h.01M11 18h9",
  breadcrumb: "M3 12h4M11 12h2M17 12h4M8 9l2 3-2 3M14 9l2 3-2 3",
  footnote: "M4 9h10M4 13h10M4 17h6M17 5l2-1v5",
  inlineEquation: "M17 5H7l5 7-5 7h10",
  synced: "M20 11a8 8 0 0 0-14.6-4.6M4 4v3.5h3.5M4 13a8 8 0 0 0 14.6 4.6M20 20v-3.5h-3.5",
  pageLink: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
  page: "M7 3h7l4 4v14H7zM14 3v4h4M10 12h5M10 16h5",
  plus: "M12 5v14M5 12h14",
  grip: "M9 6h.01M15 6h.01M9 12h.01M15 12h.01M9 18h.01M15 18h.01",
};

export function Icon({ name, size = 16 }: { name: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      aria-hidden="true"
      className="flex-none"
      fill="none"
      stroke="currentColor"
      strokeWidth={name === "grip" ? 2.5 : 1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={PATHS[name] ?? PATHS.text} />
    </svg>
  );
}
