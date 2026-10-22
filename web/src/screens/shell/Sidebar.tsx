import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { Brand } from "../../app/Brand";
import { useTheme, type Theme } from "../../app/theme";
import { useKbs } from "../../data/kbs";
import { useI18n, type Lang } from "../../i18n";
import { cx } from "../../ui/cx";
import { Icon, type IconName } from "../../ui/Icon";
import { IconButton } from "../../ui/IconButton";
import { Kbd } from "../../ui/Kbd";
import { BaseDialog, type BaseEdit } from "../bases/BaseDialog";
import { BaseSection } from "./BaseSection";
import { useShell } from "./shell";

const rowClass =
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

/** Every base as a section with its tree, the places phase B fills, and "Nova base" and "Lixeira" at the bottom. */
export function Sidebar() {
  const { t, lang, setLang } = useI18n();
  const { theme, setTheme } = useTheme();
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
      {/* Phase B: ⌘K and recents. Shown so the layout is the final one. */}
      <button type="button" disabled className={cx(rowClass, "cursor-default")}>
        <Row icon="search">{t("shell.search")}</Row>
        <Kbd>⌘K</Kbd>
      </button>
      <button type="button" disabled className={cx(rowClass, "cursor-default")}>
        <Row icon="recent">{t("shell.recent")}</Row>
      </button>

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
        <div className="mt-2 flex justify-between px-2">
          <Switch<Lang>
            label={t("app.lang.label")}
            value={lang}
            onChange={setLang}
            options={[
              { value: "ptBR", label: "PT" },
              { value: "en", label: "EN" },
            ]}
          />
          <Switch<Theme>
            label={t("app.theme.label")}
            value={theme}
            onChange={setTheme}
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
