import { useEffect, type ReactNode } from "react";
import {
  Navigate,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
  useOutletContext,
  useSearchParams,
} from "react-router-dom";
import { switchOrganization, useCurrentOrganization, type Organization } from "../../data/organizations";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
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
  bell: <path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20.5a2 2 0 0 0 4 0" />,
  gear: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1" />
    </>
  ),
  users: (
    <>
      <circle cx="9" cy="8.5" r="3" />
      <path d="M3.5 19c.7-3 2.8-4.7 5.5-4.7s4.8 1.7 5.5 4.7M15.5 5.8a3 3 0 0 1 0 5.4M17.5 14.6c1.5.6 2.6 2.1 3 4.4" />
    </>
  ),
  lock: (
    <>
      <rect x="5" y="11" width="14" height="9" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </>
  ),
  bases: <path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" />,
  shield: (
    <>
      <path d="M12 3.5l7 2.5v5.5c0 4.2-2.9 7.6-7 9-4.1-1.4-7-4.8-7-9V6z" />
      <path d="M9 12l2 2 4-4" />
    </>
  ),
  device: (
    <>
      <rect x="3.5" y="5" width="17" height="11" rx="1.5" />
      <path d="M8.5 19.5h7M12 16v3.5" />
    </>
  ),
  recent: (
    <>
      <path d="M12 7v5l3 2" />
      <circle cx="12" cy="12" r="8" />
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

/** Every member of a team sees its Geral; only its Owners and Admins configure it. A Pessoal has nothing to see. */
const team = (organization: Organization | undefined) => organization !== undefined && !organization.personal;
const configurable = (organization: Organization | undefined) =>
  team(organization) && organization!.my_role !== "member";

/**
 * The pages of Organização: the current organization for them, Geral only for a Membro, Perfil for a Pessoal.
 * `?org=` (the `invite_accepted` link) first makes that organization the current one, when the person is in it.
 */
export function OrgSettings() {
  const { organizations, current } = useCurrentOrganization();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const linked = params.get("org");
  const known = organizations?.some((organization) => organization.id === linked);
  useEffect(() => {
    if (!organizations || !linked) return;
    if (known) switchOrganization(linked);
    setParams({}, { replace: true, state: location.state });
  }, [organizations, linked, known, setParams, location.state]);

  if (!current || linked) return null;
  if (!team(current)) return <Navigate replace to="/conta/perfil" state={location.state} />;
  if (!configurable(current) && location.pathname !== "/organizacao/geral")
    return <Navigate replace to="/organizacao/geral" state={location.state} />;
  return <Outlet context={current} />;
}

/** The organization a page of Organização configures. */
export function useOrganization(): Organization {
  return useOutletContext<Organization>();
}

/** The settings' own bar in place of the sidebar, and the page of the route. Voltar and Esc go back where it opened. */
export function SettingsFrame() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const state = useLocation().state as SettingsState;
  const from = state?.from ?? "/";
  const organization = useCurrentOrganization().current;

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
        <NavLink to="/conta/notificacoes" state={{ from }} className={link}>
          <Glyph name="bell" />
          {t("notifications.title")}
        </NavLink>
        <NavLink to="/conta/seguranca" state={{ from }} className={link}>
          <Glyph name="shield" />
          {t("security.title")}
        </NavLink>
        <NavLink to="/conta/sessoes" state={{ from }} className={link}>
          <Glyph name="device" />
          {t("security.nav.sessions")}
        </NavLink>
        <NavLink to="/conta/atividade" state={{ from }} className={link}>
          <Glyph name="recent" />
          {t("security.nav.activity")}
        </NavLink>
        {team(organization) && (
          <>
            <span className="mt-3 flex h-7 items-center truncate px-2 text-12 text-text-3">{organization!.name}</span>
            <NavLink to="/organizacao/geral" state={{ from }} className={link}>
              <Glyph name="gear" />
              {t("settings.org.general")}
            </NavLink>
          </>
        )}
        {configurable(organization) && (
          <>
            <NavLink to="/organizacao/membros" state={{ from }} className={link}>
              <Glyph name="users" />
              {t("settings.org.members")}
            </NavLink>
            <NavLink to="/organizacao/acesso" state={{ from }} className={link}>
              <Glyph name="lock" />
              {t("settings.org.access")}
            </NavLink>
            <NavLink to="/organizacao/bases" state={{ from }} className={link}>
              <Glyph name="bases" />
              {t("settings.org.bases")}
            </NavLink>
            <NavLink to="/organizacao/auditoria" state={{ from }} className={link}>
              <Glyph name="recent" />
              {t("security.nav.audit")}
            </NavLink>
          </>
        )}
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

/** A section's 15 px title and what it does, with its one action at the right, over its rows. */
export function SettingsSection({
  title,
  desc,
  action,
  children,
}: {
  title: string;
  desc?: string;
  action?: { label: string; onClick: () => void; disabled?: boolean };
  children?: ReactNode;
}) {
  return (
    <section aria-label={title}>
      <div className="flex items-start justify-between gap-4 border-b border-line pb-3">
        <span>
          <h2 className="m-0 text-15 font-medium text-text">{title}</h2>
          {desc && <p className="m-0 text-13 text-text-3">{desc}</p>}
        </span>
        {action && (
          <Button size="sm" disabled={action.disabled} onClick={action.onClick}>
            {action.label}
          </Button>
        )}
      </div>
      {children}
    </section>
  );
}
