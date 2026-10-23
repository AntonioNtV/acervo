import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { SearchPalette } from "../screens/search/SearchPalette";
import { ChatPanel } from "../screens/shell/ChatPanel";
import { ShellProvider, useShell } from "../screens/shell/shell";
import { Sidebar } from "../screens/shell/Sidebar";

function Frame() {
  const { sidebarOpen } = useShell();
  const [searchOpen, setSearchOpen] = useState(false);

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
        <Outlet />
      </main>
      <ChatPanel />
      {searchOpen && <SearchPalette onClose={() => setSearchOpen(false)} />}
    </div>
  );
}

/** Sidebar · the screen of the route · the chat panel when open; ⌘K (Ctrl+K) opens the search palette anywhere. */
export function ShellFrame() {
  return (
    <ShellProvider>
      <Frame />
    </ShellProvider>
  );
}
