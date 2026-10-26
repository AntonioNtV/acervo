import { Link } from "react-router-dom";
import { useOrganizationBases } from "../../data/orgSettings";
import { useI18n } from "../../i18n";
import { SettingsPage, SettingsSection, useOrganization } from "./SettingsFrame";

/** `/organizacao/bases`: every base of the organization and who it is open to, to review in one place. */
export function OrgBases() {
  const { t } = useI18n();
  const organization = useOrganization();
  const bases = useOrganizationBases(organization.id).data;
  if (!bases) return null;
  return (
    <SettingsPage title={t("settings.org.bases")}>
      <SettingsSection
        title={bases.length === 1 ? t("settings.bases.count.one") : t("settings.bases.count", { count: bases.length })}
        desc={t("settings.bases.desc")}
      >
        {bases.map((kb) => (
          <div key={kb.id} className="flex min-h-14 items-center justify-between gap-4 border-b border-line py-2.5">
            <span className="flex min-w-0 flex-col">
              <span className="truncate text-13 text-text">{kb.icon ? `${kb.icon} ${kb.name}` : kb.name}</span>
              <span className="text-12 leading-[18px] text-text-3">
                {kb.general_access === "none"
                  ? t("settings.access.none")
                  : t("settings.bases.everyone", {
                      name: organization.name,
                      role: t(`settings.role.base.${kb.general_access}`),
                    })}
              </span>
            </span>
            {/* shortcut: opens the base, whose menu has Compartilhar; open card 09's ShareDialog here once merged. */}
            <Link
              to={`/kbs/${kb.id}`}
              className="inline-flex h-[26px] items-center rounded-[6px] border border-line-2 px-2 text-12 font-medium text-text hover:bg-subtle"
            >
              {t("settings.bases.open")}
            </Link>
          </div>
        ))}
      </SettingsSection>
    </SettingsPage>
  );
}
