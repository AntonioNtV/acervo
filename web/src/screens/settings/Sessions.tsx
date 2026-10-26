import { useErrorText } from "../../app/errors";
import { useEndOtherSessions, useEndSession, useSessions } from "../../data/sessions";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { SessionRow } from "../../ui/SessionRow";
import { relativeTime } from "../bases/when";
import { deviceText } from "./Activity";
import { SettingsPage, SettingsSection } from "./SettingsFrame";

/** `/conta/sessoes`: every browser with the account open; Encerrar ends one, the action ends all but this one. */
export default function Sessions() {
  const { t, lang } = useI18n();
  const errorText = useErrorText();
  const sessions = useSessions().data;
  const end = useEndSession();
  const endOthers = useEndOtherSessions();
  if (!sessions) return null;
  const failed = end.error ?? endOthers.error;
  const reset = () => [end, endOthers].forEach((mutation) => mutation.reset());

  return (
    <SettingsPage title={t("activity.sessions")}>
      <SettingsSection
        title={t("activity.sessions")}
        desc={t("activity.sessions.desc")}
        action={{
          label: t("activity.sessions.endOthers"),
          disabled: sessions.length < 2 || endOthers.isPending,
          onClick: () => {
            reset();
            endOthers.mutate();
          },
        }}
      >
        {sessions.map((session) => (
          <SessionRow
            key={session.id}
            device={deviceText(t, session.browser, session.system)}
            phone={/iphone|android/i.test(session.system ?? "")}
            when={session.current ? t("activity.sessions.activeNow") : relativeTime(session.last_seen_at, lang)}
            current={session.current ? t("activity.sessions.current") : undefined}
            action={
              <Button
                variant="quiet"
                size="sm"
                disabled={end.isPending}
                onClick={() => {
                  reset();
                  end.mutate(session.id);
                }}
              >
                {t("activity.sessions.end")}
              </Button>
            }
          />
        ))}
        {failed && (
          <p role="alert" className="mt-3 mb-0 text-12 text-err">
            {errorText(failed)}
          </p>
        )}
      </SettingsSection>
    </SettingsPage>
  );
}
