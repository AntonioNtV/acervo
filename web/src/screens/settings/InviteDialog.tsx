import { useState } from "react";
import { useErrorText } from "../../app/errors";
import { useInvite, type Organization, type OrgRole } from "../../data/orgSettings";
import { ApiError } from "../../data/request";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { cx } from "../../ui/cx";
import { Dialog, DialogClose } from "../../ui/Dialog";
import { Icon } from "../../ui/Icon";
import { RoleSelect } from "../../ui/RoleSelect";

// Enough to catch a typo before sending; the API checks the rest.
const looksLikeEmail = (text: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text);

/**
 * Convidar: emails, typed or pasted, become chips (on Enter, comma or space) and all get one role. Each gets a link
 * valid for 7 days.
 */
export function InviteDialog({
  organization,
  open,
  onOpenChange,
}: {
  organization: Organization;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const invite = useInvite(organization.id);
  const [emails, setEmails] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  const [role, setRole] = useState<OrgRole>("member");
  const invalid = emails.find((email) => !looksLikeEmail(email));
  const members = invite.error instanceof ApiError && invite.error.code === "already_member";

  function add(text: string): string[] {
    const typed = text.split(/[\s,;]+/).filter(Boolean);
    const next = [...emails, ...typed.filter((email) => !emails.includes(email))];
    setEmails(next);
    setDraft("");
    if (typed.length) invite.reset();
    return next;
  }

  function close(next: boolean) {
    if (!next) {
      setEmails([]);
      setDraft("");
      setRole("member");
      invite.reset();
    }
    onOpenChange(next);
  }

  function submit() {
    const all = add(draft);
    if (!all.length || all.some((email) => !looksLikeEmail(email))) return;
    invite.mutate({ emails: all, role }, { onSuccess: () => close(false) });
  }

  return (
    <Dialog
      open={open}
      onOpenChange={close}
      title={t("settings.invite.title", { name: organization.name })}
      footer={
        <>
          <DialogClose asChild>
            <Button variant="quiet">{t("settings.invite.cancel")}</Button>
          </DialogClose>
          <Button
            variant="ink"
            disabled={(!emails.length && !draft.trim()) || invalid !== undefined || invite.isPending}
            onClick={submit}
          >
            {emails.length > 1
              ? t("settings.invite.submitMany", { count: emails.length })
              : t("settings.invite.submit")}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-1.5 text-12 text-text-2">
        <span className="flex items-center justify-between">
          {t("settings.invite.emails")}
          <RoleSelect
            scope="org"
            value={role}
            roles={organization.my_role === "owner" ? undefined : ["admin", "member"]}
            onChange={setRole}
          />
        </span>
        <div
          className={cx(
            "flex min-h-[30px] flex-wrap gap-1 rounded-[7px] border bg-bg px-1 py-[3px]",
            invalid ? "border-err" : "border-line-2",
          )}
        >
          {emails.map((email) => (
            <span
              key={email}
              className={cx(
                "inline-flex h-[22px] items-center gap-1 rounded-[4px] border pr-1 pl-2 text-12",
                email === invalid ? "border-err text-err" : "border-line-2 text-text",
              )}
            >
              {email}
              <button
                type="button"
                aria-label={t("settings.invite.drop", { email })}
                className="inline-flex cursor-pointer border-0 bg-transparent p-0.5 text-text-3"
                onClick={() => setEmails(emails.filter((other) => other !== email))}
              >
                <Icon name="close" size={12} />
              </button>
            </span>
          ))}
          <input
            aria-label={t("settings.invite.emails")}
            placeholder={emails.length ? "" : t("settings.invite.placeholder")}
            autoFocus
            className="min-w-[120px] flex-1 border-0 bg-transparent px-1.5 text-13 text-text outline-none"
            value={draft}
            onChange={(event) => {
              const text = event.target.value;
              if (/[\s,;]/.test(text)) add(text);
              else setDraft(text);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                if (draft.trim()) add(draft);
                else submit();
              } else if (event.key === "Backspace" && !draft) setEmails(emails.slice(0, -1));
            }}
            onBlur={() => draft.trim() && add(draft)}
          />
        </div>
        {(invalid || invite.isError) && (
          <p role="alert" className="m-0 text-12 text-err">
            {invalid
              ? t("settings.invite.invalid", { email: invalid })
              : members
                ? t("settings.invite.members", {
                    emails: ((invite.error as ApiError).details.emails as string[] | undefined)?.join(", ") ?? "",
                  })
                : errorText(invite.error)}
          </p>
        )}
      </div>
    </Dialog>
  );
}
