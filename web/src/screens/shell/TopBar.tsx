import type { ReactNode } from "react";
import { AiMark } from "../../app/AiMark";
import { useI18n } from "../../i18n";
import { Icon } from "../../ui/Icon";
import { IconButton } from "../../ui/IconButton";
import { Breadcrumb } from "./Breadcrumb";
import { useShell } from "./shell";

type Props = {
  /** The base and node the breadcrumb leads to; a screen outside a base passes `label` instead. */
  kbId?: string;
  nodeId?: string;
  label?: string;
  /** "Salvo", "Salvando…": text in gray before the actions. */
  status?: ReactNode;
  actions?: ReactNode;
  /** The screen's ⋯ menu, last on the bar. */
  menu?: ReactNode;
};

/** The bar over every content screen: where it is, the screen's status and actions, and the chat. */
export function TopBar({ kbId, nodeId, label, status, actions, menu }: Props) {
  const { t } = useI18n();
  const { sidebarOpen, setSidebarOpen, chatOpen, setChatOpen } = useShell();
  return (
    <header className="sticky top-0 z-10 flex h-11 shrink-0 items-center justify-between gap-3 bg-bg pr-2.5 pl-3.5">
      <div className="flex min-w-0 items-center gap-1.5">
        {!sidebarOpen && (
          <IconButton aria-label={t("shell.sidebar.open")} onClick={() => setSidebarOpen(true)} className="-ml-1">
            <Icon name="expand" />
          </IconButton>
        )}
        {kbId ? <Breadcrumb kbId={kbId} nodeId={nodeId} /> : label && <span className="px-1 text-13 text-text">{label}</span>}
      </div>
      <div className="flex shrink-0 items-center gap-0.5">
        {status && <span className="px-2 text-12 text-text-3">{status}</span>}
        {actions}
        <button
          type="button"
          aria-pressed={chatOpen}
          onClick={() => setChatOpen(!chatOpen)}
          className="inline-flex h-7 cursor-pointer items-center gap-1.5 rounded-[6px] border-0 bg-transparent px-2 text-13 text-ai-text hover:bg-subtle aria-pressed:bg-subtle"
        >
          <AiMark size={16} />
          {t("shell.chat.label")}
        </button>
        {menu}
      </div>
    </header>
  );
}
