import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useMatch } from "react-router-dom";

const SIDEBAR_KEY = "acervo.sidebar";

type Shell = {
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  chatOpen: boolean;
  setChatOpen: (open: boolean) => void;
};

// Outside the shell (a screen rendered alone in a test) the bars still render, with nothing to toggle.
const ShellContext = createContext<Shell>({
  sidebarOpen: true,
  setSidebarOpen: () => {},
  chatOpen: false,
  setChatOpen: () => {},
});

function readSidebar(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_KEY) !== "closed";
  } catch {
    return true;
  }
}

/** Whether the sidebar and the chat are open; ⌘J (Ctrl+J) toggles the chat anywhere in the app. */
export function ShellProvider({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarState] = useState(readSidebar);
  const [chatOpen, setChatOpen] = useState(false);

  const setSidebarOpen = useCallback((open: boolean) => {
    setSidebarState(open);
    try {
      localStorage.setItem(SIDEBAR_KEY, open ? "open" : "closed");
    } catch {
      // The choice still holds for this session.
    }
  }, []);

  // Captured, so ⌘J reaches the chat before the editor or an open menu handles it.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && !event.altKey && event.key.toLowerCase() === "j") {
        event.preventDefault();
        event.stopPropagation();
        setChatOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, []);

  const value = useMemo(
    () => ({ sidebarOpen, setSidebarOpen, chatOpen, setChatOpen }),
    [sidebarOpen, setSidebarOpen, chatOpen],
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
