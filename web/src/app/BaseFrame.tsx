import { Outlet } from "react-router-dom";
import { BaseLayout } from "../features/tree/BaseLayout";
import { useI18n } from "../i18n";
import { Brand } from "./Brand";
import { ChatColumn } from "./ChatColumn";

export function BaseFrame() {
  const { t } = useI18n();
  return (
    <div className="flex h-full min-h-0">
      <aside
        aria-label={t("app.base.tree")}
        className="flex w-[248px] shrink-0 flex-col gap-px overflow-y-auto bg-side px-2.5 py-[18px]"
      >
        <div className="mb-4">
          <Brand />
        </div>
        <BaseLayout />
      </aside>
      <main className="min-w-[480px] flex-1 overflow-y-auto">
        <Outlet />
      </main>
      <ChatColumn />
    </div>
  );
}
