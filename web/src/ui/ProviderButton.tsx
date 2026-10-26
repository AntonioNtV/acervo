import type { ReactNode } from "react";

/** Google's own mark: its brand rules require its four colors, the one place hex sits outside the tokens. */
export function GoogleLogo() {
  return (
    <svg viewBox="0 0 24 24" width={16} height={16} aria-hidden="true">
      <path fill="#4285F4" d="M23.49 12.27c0-.79-.07-1.54-.19-2.27H12v4.51h6.47c-.29 1.48-1.14 2.73-2.4 3.58v3h3.86c2.26-2.09 3.56-5.17 3.56-8.82z" />
      <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09C3.26 21.3 7.31 24 12 24z" />
      <path fill="#FBBC05" d="M5.27 14.29c-.25-.72-.38-1.49-.38-2.29s.14-1.57.38-2.29V6.62H1.29C.47 8.24 0 10.06 0 12s.47 3.76 1.29 5.38l3.98-3.09z" />
      <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.7 1.29 6.62l3.98 3.09c.95-2.85 3.6-4.96 6.73-4.96z" />
    </svg>
  );
}

/** A passkey, in `text`. */
export function PasskeyLogo() {
  return (
    <svg
      viewBox="0 0 24 24"
      width={16}
      height={16}
      aria-hidden="true"
      className="shrink-0 fill-none stroke-current stroke-[1.5]"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="8" cy="15" r="4" />
      <path d="M11 12l8-8M16 7l2 2M14 9l2 2" />
    </svg>
  );
}

const providerClass =
  "inline-flex h-[30px] w-full cursor-pointer items-center justify-center gap-1.5 rounded-[7px] border border-line-2 bg-bg text-13 font-medium text-text no-underline hover:bg-subtle disabled:cursor-default disabled:bg-bg disabled:opacity-50";

/**
 * A full-width default button for a sign-in provider: a plain link when the provider's page takes over (`href`), a
 * button when the browser's own prompt does (`onClick`, the passkey).
 */
export function ProviderButton({
  href,
  onClick,
  disabled,
  logo,
  children,
}: {
  href?: string;
  onClick?: () => void;
  disabled?: boolean;
  logo: ReactNode;
  children: ReactNode;
}) {
  return href ? (
    <a href={href} className={providerClass}>
      {logo}
      {children}
    </a>
  ) : (
    <button type="button" onClick={onClick} disabled={disabled} className={providerClass}>
      {logo}
      {children}
    </button>
  );
}
