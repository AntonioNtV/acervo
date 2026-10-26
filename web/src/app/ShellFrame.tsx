import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { useKb, useKbs } from "../data/kbs";
import { switchOrganization, useCurrentOrganization } from "../data/organizations";
import { useI18n } from "../i18n";
import { SearchPalette } from "../screens/search/SearchPalette";
import { ShellProvider, useCurrent, useShell } from "../screens/shell/shell";
import { Sidebar } from "../screens/shell/Sidebar";

/**
 * A base in the URL that the current organization does not list: the rail switches to the base's organization, the
 * Pessoal for a base shared with the person as a guest; `noAccess` when the person cannot see it, so the base's name
 * is never shown.
 */
function useFollowBase(): { noAccess: boolean } {
  const { kbId } = useCurrent();
  const kbs = useKbs().data;
  const { organizations, current } = useCurrentOrganization();
  const missing = Boolean(kbId && kbs && !kbs.some((kb) => kb.id === kbId));
  const base = useKb(kbId, missing);
  const home = organizations?.find((org) => org.id === base.data?.organization_id);
  const target = home && !home.personal ? home.id : null;
  useEffect(() => {
    if (missing && base.data && organizations && target !== (current?.personal ? null : current?.id)) switchOrganization(target);
  }, [missing, base.data, organizations, target, current]);
  return { noAccess: missing && base.isError };
}

function Frame() {
  const { t } = useI18n();
  const { sidebarOpen } = useShell();
  const [searchOpen, setSearchOpen] = useState(false);
  const { noAccess } = useFollowBase();

  // Captured, so ⌘K reaches the palette before the editor or a focused field handles it.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && !event.altKey && event.key.toLowerCase() === "k") {
        event.preventDefault();
        event.stopPropagation();
        setSearchOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, []);

  return (
    <div className="flex h-full min-h-0">
      {sidebarOpen && <Sidebar onSearch={() => setSearchOpen(true)} />}
      <main className="flex min-w-[480px] flex-1 flex-col overflow-y-auto">
        {noAccess ? <p className="m-0 p-10 text-text-3">{t("organizations.noAccess")}</p> : <Outlet />}
      </main>
      {searchOpen && <SearchPalette onClose={() => setSearchOpen(false)} />}
    </div>
  );
}

/** Sidebar · the screen of the route; ⌘K (Ctrl+K) opens the search palette anywhere. */
export function ShellFrame() {
  return (
    <ShellProvider>
      <Frame />
    </ShellProvider>
  );
}
