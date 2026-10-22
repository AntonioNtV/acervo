import { Outlet } from "react-router-dom";
import { ChatPanel } from "../screens/shell/ChatPanel";
import { ShellProvider, useShell } from "../screens/shell/shell";
import { Sidebar } from "../screens/shell/Sidebar";

function Frame() {
  const { sidebarOpen } = useShell();
  return (
    <div className="flex h-full min-h-0">
      {sidebarOpen && <Sidebar />}
      <main className="flex min-w-[480px] flex-1 flex-col overflow-y-auto">
        <Outlet />
      </main>
      <ChatPanel />
    </div>
  );
}

/** Sidebar · the screen of the route · the chat panel when open. */
export function ShellFrame() {
  return (
    <ShellProvider>
      <Frame />
    </ShellProvider>
  );
}
