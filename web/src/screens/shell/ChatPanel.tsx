import { useSyncExternalStore } from "react";
import { AiMark } from "../../app/AiMark";
import { useI18n } from "../../i18n";
import { Icon } from "../../ui/Icon";
import { IconButton } from "../../ui/IconButton";
import { Chat } from "../chat/Chat";
import { useCurrent, useShell } from "./shell";

// Below it, a page beside the tree and the chat would be a thin column: the chat goes over the page instead.
const NARROW = "(max-width: 1099px)";

function subscribeNarrow(changed: () => void) {
  const query = window.matchMedia?.(NARROW);
  query?.addEventListener("change", changed);
  return () => query?.removeEventListener("change", changed);
}

const isNarrow = () => window.matchMedia?.(NARROW).matches ?? false;

/**
 * The chat of the open base, beside any screen, or over it in a narrow window; closed by default, opened by the top
 * bar's "Chat" or ⌘J.
 */
export function ChatPanel() {
  const { t } = useI18n();
  const { chatOpen, setChatOpen } = useShell();
  const { kbId, nodeId } = useCurrent();
  const narrow = useSyncExternalStore(subscribeNarrow, isNarrow);
  if (!chatOpen) return null;
  return (
    <aside
      aria-label={t("shell.chat.label")}
      className={
        narrow
          ? "fixed inset-y-0 right-0 flex w-[min(400px,100vw)] flex-col border-l border-line-2 bg-bg"
          : "flex w-[360px] min-w-0 shrink-0 flex-col border-l border-line bg-bg xl:w-[400px]"
      }
    >
      {kbId ? (
        // A conversation belongs to its base: another base starts from its own.
        <Chat key={kbId} kbId={kbId} nodeId={nodeId} onClose={() => setChatOpen(false)} />
      ) : (
        <>
          <div className="flex h-11 shrink-0 items-center justify-between border-b border-line pr-1.5 pl-4">
            <span className="flex items-center gap-2 font-medium">
              <AiMark size={15} />
              {t("shell.chat.label")}
            </span>
            <IconButton aria-label={t("shell.chat.close")} onClick={() => setChatOpen(false)}>
              <Icon name="close" size={15} />
            </IconButton>
          </div>
          <div className="flex flex-1 flex-col items-center justify-center gap-2 px-8 py-6 text-center">
            <AiMark size={28} />
            <span className="text-text-3">{t("chat.noBase")}</span>
          </div>
        </>
      )}
    </aside>
  );
}
