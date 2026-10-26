import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMe } from "../../data/account";
import { switchOrganization, useCurrentOrganization, type Organization } from "../../data/organizations";
import { useI18n } from "../../i18n";
import { Avatar } from "../../ui/Avatar";
import { Icon } from "../../ui/Icon";
import { OrgDialog } from "./OrgDialog";

/** The person's organizations as icons left of the sidebar, Pessoal first, the current one ringed; "+" creates one. */
export function OrgRail() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const account = useMe().data;
  const { organizations, current } = useCurrentOrganization();
  const [creating, setCreating] = useState(false);
  if (!organizations) return null;

  // Each organization's bases start at Bases: the page open belongs to the one left.
  const open = (org: Organization) => {
    switchOrganization(org.personal ? null : org.id);
    navigate("/bases");
  };

  return (
    <nav
      aria-label={t("organizations.rail")}
      className="flex w-14 shrink-0 flex-col items-center gap-2 overflow-y-auto border-r border-line bg-side py-3"
    >
      {organizations.map((org) => {
        const name = org.personal ? t("organizations.personal") : org.name;
        return (
          <button
            key={org.id}
            type="button"
            aria-label={name}
            title={name}
            aria-current={org.id === current?.id || undefined}
            onClick={() => open(org)}
            className="flex cursor-pointer rounded-[8px] border-0 bg-transparent p-0 aria-[current]:shadow-[0_0_0_2px_var(--side),0_0_0_4px_var(--text-3)]"
          >
            {org.personal ? (
              <Avatar name={account?.name ?? ""} email={account?.email} photo={null} size={32} square />
            ) : (
              <Avatar name={org.name} photo={org.logo_url} size={32} square />
            )}
          </button>
        );
      })}
      <button
        type="button"
        aria-label={t("organizations.new")}
        title={t("organizations.new")}
        onClick={() => setCreating(true)}
        className="inline-flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-[8px] border border-dashed border-line-2 bg-transparent text-text-3 hover:text-text"
      >
        <Icon name="plus" size={16} />
      </button>
      {creating && <OrgDialog onCreated={open} onClose={() => setCreating(false)} />}
    </nav>
  );
}
