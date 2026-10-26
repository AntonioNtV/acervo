import { useEffect, type ReactNode } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useI18n } from "../../i18n";
import { cx } from "../../ui/cx";
import { rowClass } from "../shell/Sidebar";

// Glyphs only this nav uses, so they stay out of Icon's set.
const GLYPHS = {
  back: <path d="M19 12H5M11 6l-6 6 6 6" />,
  user: (
    <>
      <circle cx="12" cy="8.5" r="3.5" />
      <path d="M5 20c.8-3.5 3.6-5.5 7-5.5s6.2 2 7 5.5" />
    </>
  ),
  sliders: (
    <>
      <path d="M4 7h10M18 7h2M4 17h4M12 17h8" />
      <circle cx="16" cy="7" r="2" />
      <circle cx="10" cy="17" r="2" />
    </>
  ),
};

function Glyph({ name }: { name: keyof typeof GLYPHS }) {
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
      {GLYPHS[name]}
    </svg>
  );
}

/** Where Voltar goes: the screen that opened the settings, carried in the router's state between their pages. */
export type SettingsState = { from?: string } | null;

/** The settings' own bar in place of the sidebar, and the page of the route. Voltar and Esc go back where it opened. */
export function SettingsFrame() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const state = useLocation().state as SettingsState;
  const from = state?.from ?? "/";

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      // An open menu takes Esc first and marks it handled.
      if (event.key === "Escape" && !event.defaultPrevented) navigate(from);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate, from]);

  const link = ({ isActive }: { isActive: boolean }) => cx(rowClass, "hover:bg-muted", isActive && "bg-muted text-text");
  return (
    <div className="flex h-full min-h-0">
      <nav
        aria-label={t("settings.nav")}
        className="flex w-[248px] shrink-0 flex-col gap-px overflow-y-auto border-r border-line bg-side px-1.5 pt-2 pb-2.5"
      >
        <div className="mb-1 flex h-9 items-center">
          <button type="button" onClick={() => navigate(from)} className={cx(rowClass, "cursor-pointer hover:bg-muted")}>
            <Glyph name="back" />
            {t("settings.back")}
          </button>
        </div>
        <span className="flex h-7 items-center px-2 text-12 text-text-3">{t("settings.account")}</span>
        <NavLink to="/conta/perfil" state={{ from }} className={link}>
          <Glyph name="user" />
          {t("settings.profile")}
        </NavLink>
        <NavLink to="/conta/preferencias" state={{ from }} className={link}>
          <Glyph name="sliders" />
          {t("settings.preferences")}
        </NavLink>
      </nav>
      <main className="flex min-w-[480px] flex-1 flex-col overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}

/** A settings page: its 32 px title over its sections. */
export function SettingsPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mx-auto box-border w-full max-w-[624px] px-8 pt-25 pb-16">
      <h1 className="m-0 text-32 leading-[38px] font-medium tracking-[-0.035em]">{title}</h1>
      <div className="mt-8 flex flex-col gap-10">{children}</div>
    </div>
  );
}

/** A section's 15 px title and what it does, over its rows. */
export function SettingsSection({ title, desc, children }: { title: string; desc?: string; children: ReactNode }) {
  return (
    <section aria-label={title}>
      <div className="border-b border-line pb-3">
        <h2 className="m-0 text-15 font-medium text-text">{title}</h2>
        {desc && <p className="m-0 text-13 text-text-3">{desc}</p>}
      </div>
      {children}
    </section>
  );
}
