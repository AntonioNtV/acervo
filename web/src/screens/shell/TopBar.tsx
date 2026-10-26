import type { ReactNode } from "react";
import { useI18n } from "../../i18n";
import { Icon } from "../../ui/Icon";
import { IconButton } from "../../ui/IconButton";
import { Breadcrumb } from "./Breadcrumb";
import { ShareButton } from "./ShareDialog";
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

/** The bar over every content screen: where it is, the screen's status and actions. */
export function TopBar({ kbId, nodeId, label, status, actions, menu }: Props) {
  const { t } = useI18n();
  const { sidebarOpen, setSidebarOpen } = useShell();
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
        {kbId && <ShareButton kbId={kbId} />}
        {actions}
        {menu}
      </div>
    </header>
  );
}
