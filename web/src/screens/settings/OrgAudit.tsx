import { auditCsv, useAudit, type AuditEvent } from "../../data/sessions";
import { useI18n } from "../../i18n";
import { SecurityEventRow } from "../../ui/SecurityEventRow";
import { ByDay, eventText, eventTone } from "./Activity";
import { SettingsPage, SettingsSection, useOrganization } from "./SettingsFrame";

const AREAS: Partial<Record<AuditEvent["kind"], string>> = {
  base_created: "activity.audit.area.bases",
  base_trashed: "activity.audit.area.bases",
  base_restored: "activity.audit.area.bases",
  access_changed: "activity.audit.area.bases",
  two_factor_required: "activity.audit.area.access",
};

/** `/organizacao/auditoria`: who did what in the organization in the last 90 days, and Exportar CSV. */
export default function OrgAudit() {
  const { t } = useI18n();
  const organization = useOrganization();
  const events = useAudit(organization.id).data;
  if (!events) return null;
  return (
    <SettingsPage title={t("activity.audit")}>
      <SettingsSection
        title={t("activity.audit.days")}
        action={{ label: t("activity.audit.csv"), onClick: () => window.location.assign(auditCsv(organization.id)) }}
      >
        <ByDay
          events={events}
          row={(event, time) => (
            <SecurityEventRow
              tone={eventTone(event.kind, event.data)}
              text={eventText(t, event.kind, event.data, event.actor_name ?? t("activity.audit.someone"))}
              where={t(AREAS[event.kind] ?? "activity.audit.area.organization")}
              when={time}
            />
          )}
        />
      </SettingsSection>
    </SettingsPage>
  );
}
