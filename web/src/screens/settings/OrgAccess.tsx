import { useOrganizationDetail, useUpdateOrganization } from "../../data/orgSettings";
import { useI18n } from "../../i18n";
import { SettingRow } from "../../ui/SettingRow";
import { SettingsPage, SettingsSection, useOrganization } from "./SettingsFrame";

/** `/organizacao/acesso`: whether members need two-step verification, and who sees a base when it is created. */
export function OrgAccess() {
  const { t } = useI18n();
  const organization = useOrganization();
  const update = useUpdateOrganization(organization.id);
  const passwordOnly = useOrganizationDetail(organization.id).data?.password_only ?? 0;
  return (
    <SettingsPage title={t("settings.org.access")}>
      <SettingsSection title={t("activity.security")}>
        <SettingRow
          title={t("activity.require2fa")}
          desc={
            passwordOnly === 0
              ? t("activity.require2fa.none")
              : passwordOnly === 1
                ? t("activity.require2fa.one")
                : t("activity.require2fa.many", { count: passwordOnly })
          }
          value={organization.require_two_factor ? "on" : "off"}
          onChange={(value) => update.mutate({ require_two_factor: value === "on" })}
          options={[
            { value: "off", label: t("activity.require2fa.off") },
            { value: "on", label: t("activity.require2fa.on") },
          ]}
        />
      </SettingsSection>
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
