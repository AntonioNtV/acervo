import { useState, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { Brand } from "../../app/Brand";
import { useForgetAccount } from "../../app/lastPage";
import { useTheme } from "../../app/theme";
import { useMe, useSignOut } from "../../data/account";
import { useKbs } from "../../data/kbs";
import { locale, useI18n } from "../../i18n";
import { Avatar } from "../../ui/Avatar";
import { cx } from "../../ui/cx";
import { Icon, type IconName } from "../../ui/Icon";
import { IconButton } from "../../ui/IconButton";
import { Kbd } from "../../ui/Kbd";
import { Menu, MenuItem, MenuSeparator } from "../../ui/Menu";
import { BaseDialog, type BaseEdit } from "../bases/BaseDialog";
import type { SettingsState } from "../settings/SettingsFrame";
import { usePreferences } from "../settings/usePreferences";
import { BaseSection } from "./BaseSection";
import { Favorites } from "./Favorites";
import { useShell } from "./shell";

export const rowClass =
  "flex h-7 w-full min-w-0 items-center gap-1.5 rounded-[6px] border-0 bg-transparent px-2 text-left text-13 text-text-2 no-underline";

function Row({ icon, children }: { icon: IconName; children: ReactNode }) {
  return (
    <>
      <Icon name={icon} />
      <span className="min-w-0 flex-1 truncate">{children}</span>
    </>
  );
}

function Switch<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div role="group" aria-label={label} className="flex gap-2.5">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
          className="cursor-pointer border-0 bg-transparent p-0 text-12 text-text-3 hover:text-text aria-pressed:text-text"
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/** The person at the foot: photo or initials and name, opening Conta and Sair. */
function AccountRow() {
  const { t } = useI18n();
  const forget = useForgetAccount();
  const account = useMe().data;
  const signOut = useSignOut();
  const navigate = useNavigate();
  const { pathname, search } = useLocation();
  if (!account) return null;
  return (
    <Menu
      label={t("settings.account.menu")}
      width={236}
      trigger={
        <button type="button" className={cx(rowClass, "cursor-pointer hover:bg-muted data-[state=open]:bg-muted")}>
          <Avatar name={account.name} email={account.email} photo={account.photo_url} />
          <span className="min-w-0 flex-1 truncate">{account.name || account.email}</span>
        </button>
      }
    >
      <div className="truncate px-2.5 pt-1 pb-0.5 text-12 text-text-3">{account.email}</div>
      <MenuItem
        onSelect={() => navigate("/conta/perfil", { state: { from: pathname + search } satisfies SettingsState })}
      >
        {t("settings.account")}
      </MenuItem>
      <MenuSeparator />
      <MenuItem
        onSelect={() =>
          signOut.mutate(undefined, {
            onSuccess: () => {
              // Replaced, and the account forgotten, so Back cannot show its pages again.
              navigate("/entrar", { replace: true });
              forget();
            },
          })
        }
      >
        {t("settings.signOut")}
      </MenuItem>
    </Menu>
  );
}

/** The favorites, every base as a section with its tree, and "Nova base" and "Lixeira" at the bottom. */
export function Sidebar({ onSearch }: { onSearch?: () => void }) {
  const { t, lang } = useI18n();
  const { theme } = useTheme();
  const setPreferences = usePreferences();
  const { setSidebarOpen } = useShell();
  const kbs = useKbs();
  const [edit, setEdit] = useState<BaseEdit | null>(null);

  return (
    <nav
      aria-label={t("shell.nav")}
      className="flex w-[248px] shrink-0 flex-col gap-px overflow-y-auto border-r border-line bg-side px-1.5 pt-2 pb-2.5"
    >
      <div className="mb-1 flex h-9 items-center justify-between pr-1 pl-2">
        <Brand />
        <IconButton aria-label={t("shell.sidebar.close")} onClick={() => setSidebarOpen(false)}>
          <Icon name="collapse" />
        </IconButton>
      </div>
      <NavLink to="/bases" className={({ isActive }) => cx(rowClass, "hover:bg-muted", isActive && "bg-muted text-text")}>
        <Row icon="bases">{t("bases.title")}</Row>
      </NavLink>
      <button type="button" onClick={onSearch} className={cx(rowClass, "cursor-pointer hover:bg-muted")}>
        <Row icon="search">{t("shell.search")}</Row>
        <Kbd>⌘K</Kbd>
      </button>
      <Favorites />

      {kbs.isError && <p className="m-0 px-2 py-1 text-12 text-err">{t("bases.error.load")}</p>}
      {kbs.data?.map((kb) => <BaseSection key={kb.id} kb={kb} onEdit={setEdit} />)}

      <div className="mt-auto flex flex-col gap-px pt-3">
        <button type="button" onClick={() => setEdit({ mode: "create" })} className={cx(rowClass, "cursor-pointer hover:bg-muted")}>
          <Row icon="plus">{t("bases.new")}</Row>
        </button>
        <NavLink
          to="/lixeira"
          className={({ isActive }) => cx(rowClass, "hover:bg-muted", isActive && "bg-muted text-text")}
        >
          <Row icon="trash">{t("shell.trash")}</Row>
        </NavLink>
        <AccountRow />
        <div className="mt-2 flex justify-between px-2">
          <Switch
            label={t("app.lang.label")}
            value={locale(lang)}
            onChange={(language) => setPreferences({ language })}
            options={[
              { value: "pt-BR", label: "PT" },
              { value: "en", label: "EN" },
            ]}
          />
          <Switch
            label={t("app.theme.label")}
            value={theme}
            onChange={(choice) => setPreferences({ theme: choice })}
            options={[
              { value: "light", label: t("app.theme.light") },
              { value: "dark", label: t("app.theme.dark") },
            ]}
          />
        </div>
      </div>

      {edit && <BaseDialog key={edit.mode} edit={edit} onClose={() => setEdit(null)} />}
    </nav>
  );
}
