import { useMe } from "../../data/account";
import { useI18n } from "../../i18n";
import { SettingRow } from "../../ui/SettingRow";
import { SettingsPage, SettingsSection } from "./SettingsFrame";
import { usePreferences } from "./usePreferences";

/** `/conta/preferencias`: theme, page width, language and start page, each saved on the account as it changes. */
export function Preferences() {
  const { t } = useI18n();
  const preferences = useMe().data?.preferences;
  const set = usePreferences();
  if (!preferences) return null;
  return (
    <SettingsPage title={t("settings.preferences")}>
      <SettingsSection title={t("settings.appearance")} desc={t("settings.appearance.desc")}>
        <SettingRow
          title={t("settings.theme")}
          desc={t("settings.theme.desc")}
          value={preferences.theme}
          onChange={(theme) => set({ theme })}
          options={[
            { value: "light", label: t("app.theme.light") },
            { value: "dark", label: t("app.theme.dark") },
            { value: "system", label: t("settings.theme.system") },
          ]}
        />
        <SettingRow
          title={t("settings.width")}
          desc={t("settings.width.desc")}
          value={preferences.page_width}
          onChange={(width) => set({ page_width: width })}
          options={[
            { value: "default", label: t("settings.width.default") },
            { value: "wide", label: t("settings.width.wide") },
          ]}
        />
      </SettingsSection>
      <SettingsSection title={t("settings.languageAndStart")}>
        <SettingRow
          title={t("app.lang.label")}
          value={preferences.language}
          onChange={(language) => set({ language })}
          options={[
            { value: "pt-BR", label: "Português (Brasil)" },
            { value: "en", label: "English" },
          ]}
        />
        <SettingRow
          title={t("settings.start")}
          value={preferences.start_page}
          onChange={(start) => set({ start_page: start })}
          options={[
            { value: "last", label: t("settings.start.last") },
            { value: "bases", label: t("bases.title") },
          ]}
        />
      </SettingsSection>
    </SettingsPage>
  );
}
