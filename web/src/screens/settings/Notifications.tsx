import type { ReactNode } from "react";
import { useMe } from "../../data/account";
import { useI18n } from "../../i18n";
import { SettingsPage, SettingsSection } from "./SettingsFrame";
import { usePreferences } from "./usePreferences";

/** SettingRow's layout with a checkbox or a fixed value at the right, the two controls only this page uses. */
function EmailRow({ title, desc, children }: { title: string; desc: string; children: ReactNode }) {
  return (
    <div className="flex min-h-14 items-center justify-between gap-4 border-b border-line py-2.5">
      <span className="flex min-w-0 flex-col">
        <span className="text-13 text-text">{title}</span>
        <span className="text-12 leading-[18px] text-text-3">{desc}</span>
      </span>
      {children}
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (on: boolean) => void }) {
  return (
    <input
      type="checkbox"
      aria-label={label}
      checked={checked}
      onChange={(event) => onChange(event.target.checked)}
      className="m-0 mr-1.5 size-[15px] cursor-pointer accent-ink"
    />
  );
}

/** `/conta/notificacoes`: which emails the account gets, each saved on the account as it changes. */
export function Notifications() {
  const { t } = useI18n();
  const me = useMe().data;
  const set = usePreferences();
  if (!me) return null;
  const { preferences } = me;
  return (
    <SettingsPage title={t("notifications.title")}>
      <SettingsSection title={t("notifications.emails")} desc={t("notifications.emails.desc", { email: me.email })}>
        <EmailRow title={t("notifications.invites")} desc={t("notifications.invites.desc")}>
          <Toggle
            label={t("notifications.invites")}
            checked={preferences.notify_invites}
            onChange={(on) => set({ notify_invites: on })}
          />
        </EmailRow>
        <EmailRow title={t("notifications.followed")} desc={t("notifications.followed.desc")}>
          <Toggle
            label={t("notifications.followed")}
            checked={preferences.notify_followed}
            onChange={(on) => set({ notify_followed: on })}
          />
        </EmailRow>
        <EmailRow title={t("notifications.security")} desc={t("notifications.security.desc")}>
          <span className="text-12 text-text-3">{t("notifications.always")}</span>
        </EmailRow>
      </SettingsSection>
    </SettingsPage>
  );
}
