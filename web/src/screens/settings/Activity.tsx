import { Fragment, type ReactNode } from "react";
import { useActivity, type SecurityEvent } from "../../data/sessions";
import { useI18n } from "../../i18n";
import type { Tone } from "../../ui/Dot";
import { SecurityEventRow } from "../../ui/SecurityEventRow";
import { dayLabel, timeOf } from "../page/format";
import { SettingsPage, SettingsSection } from "./SettingsFrame";

type T = ReturnType<typeof useI18n>["t"];
type Kind = SecurityEvent["kind"];

const FAILED: readonly Kind[] = ["wrong_password", "wrong_code", "locked_out", "passkey_refused", "base_trashed"];
const TURNED_OFF: readonly Kind[] = [
  "two_factor_off",
  "passkey_removed",
  "google_unlinked",
  "invite_revoked",
  "role_changed",
  "removed",
];

/** `err` for a failure, `warn` for something taken away; turning the 2FA requirement off is taken away too. */
export function eventTone(kind: Kind, data: Record<string, unknown>): Tone {
  if (FAILED.includes(kind)) return "err";
  if (TURNED_OFF.includes(kind) || (kind === "two_factor_required" && !data.on)) return "warn";
  return "ok";
}

/** "Chrome no macOS"; only the browser when the system is unknown. */
export function deviceText(t: T, browser: string | null, system: string | null): string {
  if (!browser) return t("activity.device.unknown");
  return system ? t("activity.device", { browser, system }) : browser;
}

/** What a line says happened; `actor` is who did it, for the audit's lines. */
export function eventText(t: T, kind: Kind, data: Record<string, unknown>, actor = ""): string {
  const text = (key: string) => String(data[key] ?? "");
  const role = (key: string) =>
    t(data.base ? `settings.role.base.${text(key)}` : `settings.role.org.${text(key)}`);
  const vars = { actor, email: text("email"), base: text("base"), member: text("member"), role: role("role") };
  switch (kind) {
    case "signed_in":
    case "two_factor_on":
    case "two_factor_off":
      return t(`activity.${kind}.${text("method")}`);
    case "session_ended":
      return data.others
        ? t("activity.session_ended.others")
        : t("activity.session_ended", {
            device: deviceText(t, data.browser as string | null, data.system as string | null),
          });
    case "invited":
    case "joined":
      return t(data.base ? `activity.${kind}.base` : `activity.${kind}`, vars);
    case "role_changed":
      return t("activity.role_changed", { ...vars, old: t(`settings.role.org.${text("old_role")}`) });
    case "access_changed":
      if ("general_access" in data)
        return t("activity.access_changed.general", { ...vars, access: t(`settings.access.${text("general_access")}`) });
      return t(data.role ? "activity.access_changed.member" : "activity.access_changed.removed", vars);
    case "two_factor_required":
      return t(data.on ? "activity.two_factor_required.on" : "activity.two_factor_required.off", vars);
    default:
      return t(`activity.${kind}`, { ...vars, to: text("to"), passkey: text("passkey") });
  }
}

/** Lines grouped by day, newest first, as in a page's history. */
export function ByDay<E extends { id: string; created_at: string }>({
  events,
  row,
}: {
  events: E[];
  row: (event: E, time: string) => ReactNode;
}) {
  const { t, lang } = useI18n();
  if (events.length === 0) return <p className="m-0 py-4 text-13 text-text-3">{t("activity.empty")}</p>;
  return events.map((event, index) => {
    const day = dayLabel(event.created_at, lang, t);
    const first = index === 0 || dayLabel(events[index - 1]!.created_at, lang, t) !== day;
    return (
      <Fragment key={event.id}>
        {first && <h3 className="m-0 px-2 pt-4 pb-1 text-12 font-normal text-text-3">{day}</h3>}
        {row(event, timeOf(event.created_at, lang))}
      </Fragment>
    );
  });
}

/** `/conta/atividade`: the account's sign-ins and security changes of the last 90 days. */
export default function Activity() {
  const { t } = useI18n();
  const events = useActivity().data;
  if (!events) return null;
  return (
    <SettingsPage title={t("activity.activity")}>
      <SettingsSection title={t("activity.activity")} desc={t("activity.activity.desc")}>
        <ByDay
          events={events}
          row={(event, time) => (
            <SecurityEventRow
              tone={eventTone(event.kind, event.data)}
              text={eventText(t, event.kind, event.data)}
              where={event.browser ? deviceText(t, event.browser, event.system) : undefined}
              when={time}
            />
          )}
        />
      </SettingsSection>
    </SettingsPage>
  );
}
