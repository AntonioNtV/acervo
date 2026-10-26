import type { ReactNode } from "react";
import { useI18n } from "../i18n";
import { Dot } from "./Dot";
import { GoogleLogo, PasskeyLogo } from "./ProviderButton";

// Glyphs only these rows use, so they stay out of Icon's set.
const GLYPHS = {
  lock: (
    <>
      <rect x="5" y="11" width="14" height="9" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </>
  ),
  chat: <path d="M4 18.5l1.2-3.6A8 8 0 1 1 8.6 18z" />,
  mail: (
    <>
      <rect x="3.5" y="5.5" width="17" height="13" rx="2" />
      <path d="M4 7l8 6 8-6" />
    </>
  ),
};

export type MethodIcon = keyof typeof GLYPHS | "google" | "passkey";

/** The icon of a way to sign in or confirm it, 16 px in `text-3`; Google keeps its own colors. */
export function MethodGlyph({ icon }: { icon: MethodIcon }) {
  if (icon === "google") return <GoogleLogo />;
  if (icon === "passkey") return <PasskeyLogo />;
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
      {GLYPHS[icon]}
    </svg>
  );
}

/**
 * A way to sign in or to confirm signing in: its name and detail, on (an `ok` dot and Ativo) or off (Desativado), and
 * its actions at the right. Never a switch.
 */
export function SecurityMethodRow({
  icon,
  name,
  detail,
  on,
  children,
}: {
  icon: MethodIcon;
  name: string;
  detail: string;
  on: boolean;
  /** The buttons: default sm to turn on or change, quiet sm to remove or turn off. */
  children?: ReactNode;
}) {
  const { t } = useI18n();
  return (
    <div className="flex min-h-14 items-center gap-3 border-b border-line py-2.5">
      <span className="inline-flex w-7 shrink-0 justify-center text-text-3">
        <MethodGlyph icon={icon} />
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-13 text-text">{name}</span>
        <span className="truncate text-12 leading-[18px] text-text-3">{detail}</span>
      </span>
      {on ? (
        <Dot tone="ok">{t("security.on")}</Dot>
      ) : (
        <span className="text-12 whitespace-nowrap text-text-3">{t("security.off")}</span>
      )}
      {children}
    </div>
  );
}
