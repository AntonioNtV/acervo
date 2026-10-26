import { useMe } from "../../data/account";
import { useI18n } from "../../i18n";
import { SettingRow } from "../../ui/SettingRow";
import { SettingsPage, SettingsSection } from "./SettingsFrame";
import { usePreferences } from "./usePreferences";

/** "Sao Paulo (GMT-3)": the zone's city and its offset now. */
function zoneLabel(zone: string): string {
  const offset = new Intl.DateTimeFormat("en", { timeZone: zone, timeZoneName: "shortOffset" })
    .formatToParts()
    .find((part) => part.type === "timeZoneName")?.value;
  return `${zone.split("/").at(-1)!.replaceAll("_", " ")} (${offset})`;
}

let zones: { value: string; label: string }[] | undefined;

/** Every IANA zone the browser knows, and the account's own when it is an alias outside that list. */
function zoneOptions(current: string) {
  zones ??= Intl.supportedValuesOf("timeZone").map((zone) => ({ value: zone, label: zoneLabel(zone) }));
  return zones.some((zone) => zone.value === current) ? zones : [{ value: current, label: zoneLabel(current) }, ...zones];
}

/** `/conta/preferencias`: theme, page width, language, time zone and start page, each saved on the account as it changes. */
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
          title={t("settings.timezone")}
          desc={t("settings.timezone.desc")}
          value={preferences.timezone}
          onChange={(timezone) => set({ timezone })}
          options={zoneOptions(preferences.timezone)}
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
