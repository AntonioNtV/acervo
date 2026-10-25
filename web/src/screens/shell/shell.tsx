import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { useMatch } from "react-router-dom";

const SIDEBAR_KEY = "acervo.sidebar";

type Shell = {
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
};

// Outside the shell (a screen rendered alone in a test) the bars still render, with nothing to toggle.
const ShellContext = createContext<Shell>({
  sidebarOpen: true,
  setSidebarOpen: () => {},
});

function readSidebar(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_KEY) !== "closed";
  } catch {
    return true;
  }
}

/** Whether the sidebar is open, remembered across visits. */
export function ShellProvider({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarState] = useState(readSidebar);

  const setSidebarOpen = useCallback((open: boolean) => {
    setSidebarState(open);
    try {
      localStorage.setItem(SIDEBAR_KEY, open ? "open" : "closed");
    } catch {
      // The choice still holds for this session.
    }
  }, []);

  const value = useMemo(
    () => ({ sidebarOpen, setSidebarOpen }),
    [sidebarOpen, setSidebarOpen],
  );
  return <ShellContext.Provider value={value}>{children}</ShellContext.Provider>;
}

export function useShell(): Shell {
  return useContext(ShellContext);
}

/** The base and node of the current URL, read from anywhere in the shell (a layout route has no child params). */
export function useCurrent(): { kbId?: string; nodeId?: string } {
  const node = useMatch("/kbs/:kbId/n/:nodeId");
  const base = useMatch("/kbs/:kbId");
  return { kbId: node?.params.kbId ?? base?.params.kbId, nodeId: node?.params.nodeId };
}
