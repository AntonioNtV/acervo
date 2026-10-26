import { useUpdateOrganization } from "../../data/orgSettings";
import { useI18n } from "../../i18n";
import { SettingRow } from "../../ui/SettingRow";
import { SettingsPage, SettingsSection, useOrganization } from "./SettingsFrame";

/** `/organizacao/acesso`: for now only who sees a base when it is created. */
export function OrgAccess() {
  const { t } = useI18n();
  const organization = useOrganization();
  const update = useUpdateOrganization(organization.id);
  return (
    <SettingsPage title={t("settings.org.access")}>
      <SettingsSection title={t("settings.org.bases")}>
        <SettingRow
          title={t("settings.access.new")}
          desc={t("settings.access.new.desc")}
          value={organization.new_base_access}
          onChange={(access) => update.mutate({ new_base_access: access })}
          options={[
            { value: "reader", label: t("settings.access.reader") },
            { value: "editor", label: t("settings.access.editor") },
            { value: "none", label: t("settings.access.none") },
          ]}
        />
      </SettingsSection>
    </SettingsPage>
  );
}
