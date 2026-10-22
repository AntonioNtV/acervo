import { NavLink, Outlet } from "react-router-dom";
import { useI18n, type Lang } from "../i18n";
import { cx } from "../ui/cx";
import { Brand } from "./Brand";
import { useTheme, type Theme } from "./theme";

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

export function IndexFrame() {
  const { t, lang, setLang } = useI18n();
  const { theme, setTheme } = useTheme();
  const navClass = ({ isActive }: { isActive: boolean }) =>
    cx(
      "flex h-[30px] items-center rounded-[6px] px-2.5 no-underline",
      isActive ? "bg-muted text-text" : "text-text-3 hover:text-text",
    );

  return (
    <div className="flex min-h-full">
      <aside aria-label={t("app.nav.label")} className="flex w-60 shrink-0 flex-col gap-px bg-side px-2.5 py-[18px]">
        <div className="mb-6">
          <Brand />
        </div>
        <NavLink to="/" end className={navClass}>
          {t("app.nav.bases")}
        </NavLink>
        <NavLink to="/lixeira" className={navClass}>
          {t("app.nav.trash")}
        </NavLink>
        <div className="mt-auto flex justify-between px-2.5">
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
      </aside>
      <main className="min-w-0 flex-1">
        <div className="mx-auto max-w-[1040px] px-16 pt-[72px] pb-16">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
