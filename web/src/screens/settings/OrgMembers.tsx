import { useState } from "react";
import { useErrorText } from "../../app/errors";
import { useMe } from "../../data/account";
import {
  useChangeRole,
  useInvite,
  useMembers,
  useOrgInvites,
  useRemoveMember,
  useResendInvite,
  useRevokeInvite,
  type Invite,
  type OrgRole,
} from "../../data/orgSettings";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { MemberRow } from "../../ui/MemberRow";
import { RoleSelect } from "../../ui/RoleSelect";
import { InviteDialog } from "./InviteDialog";
import { SettingsPage, SettingsSection, useOrganization } from "./SettingsFrame";

const DAY_MS = 24 * 60 * 60 * 1000;

/** `/organizacao/membros`: the members with their roles, then the pending invites, and Convidar. */
export function OrgMembers() {
  const { t } = useI18n();
  const errorText = useErrorText();
  const organization = useOrganization();
  const me = useMe().data;
  const members = useMembers(organization.id).data;
  const invites = useOrgInvites(organization.id).data;
  const changeRole = useChangeRole(organization.id);
  const removeMember = useRemoveMember(organization.id);
  const reinvite = useInvite(organization.id);
  const resend = useResendInvite(organization.id);
  const revoke = useRevokeInvite(organization.id);
  const [inviting, setInviting] = useState(false);
  if (!members || !invites || !me) return null;

  const owner = organization.my_role === "owner";
  // Only an Owner hands out or takes back the Owner role.
  const roles: readonly OrgRole[] | undefined = owner ? undefined : ["admin", "member"];
  const owners = members.filter((member) => member.role === "owner").length;
  const sorted = [...members].sort(
    (a, b) => Number(b.account_id === me.id) - Number(a.account_id === me.id) || a.name.localeCompare(b.name),
  );
  const failed = [changeRole, removeMember, reinvite, resend, revoke].find((mutation) => mutation.isError)?.error;
  const reset = () => [changeRole, removeMember, reinvite, resend, revoke].forEach((mutation) => mutation.reset());

  const note = (invite: Invite) => {
    const days = Math.ceil((Date.parse(invite.expires_at) - Date.now()) / DAY_MS);
    if (days <= 0) return t("settings.members.expired");
    return days === 1 ? t("settings.members.expires.one") : t("settings.members.expires", { days });
  };

  return (
    <SettingsPage title={t("settings.org.members")}>
      <SettingsSection
        title={
          members.length === 1
            ? t("settings.members.count.one")
            : t("settings.members.count", { count: members.length })
        }
        desc={
          invites.length === 0
            ? undefined
            : invites.length === 1
              ? t("settings.members.pending.one")
              : t("settings.members.pending", { count: invites.length })
        }
        action={{ label: t("settings.members.invite"), onClick: () => setInviting(true) }}
      >
        {sorted.map((member) => {
          const role = member.role as OrgRole;
          const you = member.account_id === me.id;
          return (
            <MemberRow
              key={member.account_id}
              name={member.name}
              email={member.email}
              photo={member.photo_url}
              you={you ? t("settings.members.you") : undefined}
              role={
                <RoleSelect
                  scope="org"
                  value={role}
                  roles={roles}
                  disabled={(role === "owner" && (owners === 1 || !owner)) || changeRole.isPending}
                  onChange={(next) => {
                    reset();
                    if (next !== role) changeRole.mutate({ accountId: member.account_id, role: next });
                  }}
                  onRemove={
                    you
                      ? undefined
                      : () => {
                          reset();
                          removeMember.mutate(member.account_id);
                        }
                  }
                />
              }
            />
          );
        })}
        {invites.map((invite) => {
          const role = invite.role as OrgRole;
          return (
            <MemberRow
              key={invite.id}
              name=""
              email={invite.email}
              note={note(invite)}
              actions={
                <Button
                  variant="quiet"
                  size="sm"
                  disabled={resend.isPending}
                  onClick={() => {
                    reset();
                    resend.mutate(invite.id);
                  }}
                >
                  {t("settings.members.resend")}
                </Button>
              }
              role={
                <RoleSelect
                  scope="org"
                  value={role}
                  roles={roles}
                  disabled={role === "owner" && !owner}
                  onChange={(next) => {
                    reset();
                    // A new invite with another role replaces the live one.
                    if (next !== role) reinvite.mutate({ emails: [invite.email], role: next });
                  }}
                  onRemove={() => {
                    reset();
                    revoke.mutate(invite.id);
                  }}
                />
              }
            />
          );
        })}
        {failed && (
          <p role="alert" className="mt-3 mb-0 text-12 text-err">
            {errorText(failed, {
              last_owner: t("settings.members.lastOwner"),
              too_many_attempts: t("settings.members.wait"),
            })}
          </p>
        )}
      </SettingsSection>
      <InviteDialog organization={organization} open={inviting} onOpenChange={setInviting} />
    </SettingsPage>
  );
}
