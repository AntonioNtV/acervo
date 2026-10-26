import { useState, type FormEvent, type ReactNode } from "react";
import type { KbSummary } from "../../api/client";
import { useErrorText } from "../../app/errors";
import { useMe } from "../../data/account";
import {
  useBaseAccess,
  useBaseInvites,
  useInviteToBase,
  useRemoveFromBase,
  useResendInvite,
  useRevokeInvite,
  useSetBaseRole,
  useSetGeneralAccess,
  type BaseMember,
  type BaseRole,
  type GeneralAccess,
  type Invite,
} from "../../data/access";
import { useKbs } from "../../data/kbs";
import { useOrganizations } from "../../data/organizations";
import { useI18n } from "../../i18n";
import { Avatar } from "../../ui/Avatar";
import { Button } from "../../ui/Button";
import { Dialog, DialogClose } from "../../ui/Dialog";
import { Icon } from "../../ui/Icon";
import { Input } from "../../ui/Input";
import { RoleSelect } from "../../ui/RoleSelect";

const DAY_MS = 24 * 60 * 60 * 1000;

function Row({
  avatar,
  title,
  note,
  children,
}: {
  avatar: ReactNode;
  title: ReactNode;
  note: string;
  children: ReactNode;
}) {
  return (
    <li className="flex min-h-14 items-center gap-2.5 border-b border-line last:border-b-0">
      {avatar}
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-13 text-text">{title}</span>
        <span className="truncate text-12 leading-[18px] text-text-3">{note}</span>
      </span>
      {children}
    </li>
  );
}

/**
 * Who reaches a base: the organization's general access (not in a Pessoal), the people added with their base role,
 * the invites still pending, and a field to add more. Every change applies at once; Concluído only closes.
 */
export function ShareDialog({ kb, onClose }: { kb: KbSummary; onClose: () => void }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const me = useMe().data;
  const org = useOrganizations().data?.find((candidate) => candidate.id === kb.organization_id);
  const access = useBaseAccess(kb.id);
  const invites = useBaseInvites(kb.id).data ?? [];
  const setGeneral = useSetGeneralAccess(kb.id);
  const invite = useInviteToBase(kb.id);
  const setRole = useSetBaseRole(kb.id);
  const remove = useRemoveFromBase(kb.id);
  const resend = useResendInvite(kb.id);
  const revoke = useRevokeInvite(kb.id);
  const [emails, setEmails] = useState("");
  const [addRole, setAddRole] = useState<BaseRole>("editor");
  const [copied, setCopied] = useState(false);

  const failed = [setGeneral, invite, setRole, remove, resend, revoke].find((change) => change.isError)?.error;

  const members = [...(access.data?.members ?? [])].sort(
    (a, b) => Number(b.account_id === me?.id) - Number(a.account_id === me?.id) || a.name.localeCompare(b.name),
  );

  const add = (event: FormEvent) => {
    event.preventDefault();
    const list = emails.split(/[\s,;]+/).filter(Boolean);
    if (list.length) invite.mutate({ emails: list, role: addRole }, { onSuccess: () => setEmails("") });
  };

  const copyLink = () =>
    void navigator.clipboard.writeText(`${window.location.origin}/kbs/${kb.id}`).then(() => setCopied(true));

  const pendingNote = (item: Invite) => {
    const days = Math.ceil((Date.parse(item.expires_at) - Date.now()) / DAY_MS);
    if (days <= 0) return t("sharing.expired");
    return t(days === 1 ? "sharing.pending.one" : "sharing.pending.other", { n: days });
  };

  const memberRow = (member: BaseMember) => (
    <Row
      key={member.account_id}
      avatar={<Avatar name={member.name} email={member.email} photo={member.photo_url} size={28} />}
      title={
        <>
          {member.name || member.email}
          {member.account_id === me?.id && <span className="text-text-3"> {t("sharing.you")}</span>}
        </>
      }
      note={member.email}
    >
      <RoleSelect
        label={t("sharing.role.of", { name: member.name || member.email })}
        scope="base"
        value={member.role as BaseRole}
        onChange={(role) => setRole.mutate({ accountId: member.account_id, role })}
        onRemove={() => remove.mutate(member.account_id)}
      />
    </Row>
  );

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={t("sharing.title", { name: kb.name })}
      footer={
        <>
          <Button variant="quiet" className="mr-auto" onClick={copyLink}>
            <Icon name="link" size={16} />
            {t(copied ? "sharing.link.copied" : "sharing.link.copy")}
          </Button>
          <DialogClose asChild>
            <Button>{t("sharing.done")}</Button>
          </DialogClose>
        </>
      }
    >
      <form onSubmit={add} className="flex items-center gap-1.5">
        <Input
          aria-label={t("sharing.add.label")}
          placeholder={t("sharing.add.label")}
          value={emails}
          onChange={(event) => {
            setEmails(event.target.value);
            invite.reset();
          }}
        />
        {emails.trim() && (
          <>
            <RoleSelect
              label={t("sharing.role.of", { name: emails.trim() })}
              scope="base"
              value={addRole}
              onChange={setAddRole}
            />
            <Button type="submit" disabled={invite.isPending}>
              {t("sharing.add.submit")}
            </Button>
          </>
        )}
      </form>
      {failed !== undefined && (
        <p role="alert" className="m-0 text-12 text-err">
          {errorText(failed)}
        </p>
      )}
      {access.isPending ? (
        <p className="m-0 text-text-3">{t("sharing.loading")}</p>
      ) : access.isError ? (
        <p className="m-0 text-err">{errorText(access.error)}</p>
      ) : (
        <ul aria-label={t("sharing.people")} className="m-0 flex max-h-[360px] list-none flex-col overflow-y-auto p-0">
          {org && !org.personal && (
            <GeneralRow
              org={org.name}
              value={access.data.general_access}
              onChange={(next) => setGeneral.mutate(next)}
            />
          )}
          {members.map(memberRow)}
          {invites.map((item) => (
            <Row
              key={item.id}
              avatar={<Avatar name="" email={item.email} photo={null} size={28} />}
              title={item.email}
              note={pendingNote(item)}
            >
              <Button variant="quiet" size="sm" disabled={resend.isPending} onClick={() => resend.mutate(item.id)}>
                {t("sharing.resend")}
              </Button>
              <RoleSelect
                label={t("sharing.role.of", { name: item.email })}
                scope="base"
                value={item.role as BaseRole}
                onRemove={() => revoke.mutate(item.id)}
              />
            </Row>
          ))}
        </ul>
      )}
    </Dialog>
  );
}

/** "Todos de <organização>" as Leitor or Editor, or only the people added. */
function GeneralRow({
  org,
  value,
  onChange,
}: {
  org: string;
  value: GeneralAccess;
  onChange: (next: GeneralAccess) => void;
}) {
  const { t } = useI18n();
  const everyone = value !== "none";
  return (
    <Row
      avatar={<Avatar name={org} photo={null} size={28} />}
      title={everyone ? t("sharing.general.everyone", { org }) : t("sharing.general.restricted")}
      note={t(everyone ? "sharing.general.everyone.hint" : "sharing.general.restricted.hint")}
    >
      <RoleSelect
        label={t("sharing.general")}
        value={value}
        shown={everyone ? undefined : t("sharing.general.change")}
        scope="general"
        onChange={onChange}
      />
    </Row>
  );
}

/** Compartilhar on a content screen's bar, for the base's Admins. */
export function ShareButton({ kbId }: { kbId: string }) {
  const { t } = useI18n();
  const kb = useKbs().data?.find((summary) => summary.id === kbId);
  const [open, setOpen] = useState(false);
  if (kb?.my_role !== "admin") return null;
  return (
    <>
      <Button variant="quiet" size="sm" onClick={() => setOpen(true)}>
        {t("sharing.share")}
      </Button>
      {open && <ShareDialog kb={kb} onClose={() => setOpen(false)} />}
    </>
  );
}
