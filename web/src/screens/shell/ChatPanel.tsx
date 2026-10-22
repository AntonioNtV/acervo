import { AiMark } from "../../app/AiMark";
import { useI18n } from "../../i18n";
import { Icon } from "../../ui/Icon";
import { IconButton } from "../../ui/IconButton";
import { TextTabs } from "../../ui/TextTabs";
import { useShell } from "./shell";

/**
 * The chat arrives in F2; until then the panel only holds its place, everything disabled. Closed by default, opened by
 * the top bar's "Chat" or ⌘J.
 */
export function ChatPanel() {
  const { t } = useI18n();
  const { chatOpen, setChatOpen } = useShell();
  if (!chatOpen) return null;
  return (
    <aside
      aria-label={t("shell.chat.label")}
      className="flex w-[360px] min-w-0 shrink-0 flex-col border-l border-line bg-bg xl:w-[400px]"
    >
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-line pr-2 pl-4">
        <span className="flex items-center gap-2 font-medium">
          <AiMark size={16} />
          {t("shell.chat.label")}
        </span>
        <span className="flex items-center gap-2.5">
          <TextTabs
            label={t("shell.chat.mode")}
            value="capture"
            onChange={() => {}}
            disabled
            options={[
              { value: "capture", label: t("shell.chat.capture") },
              { value: "ask", label: t("shell.chat.ask") },
            ]}
          />
          <IconButton aria-label={t("shell.chat.close")} onClick={() => setChatOpen(false)}>
            <Icon name="close" />
          </IconButton>
        </span>
      </div>
      <div className="flex flex-1 flex-col items-center justify-center gap-2 px-8 py-6 text-center">
        <AiMark size={28} />
        <span className="text-15 font-medium">{t("shell.chat.soon")}</span>
        <span className="text-text-3">{t("shell.chat.soonText")}</span>
      </div>
      <div className="m-3 flex flex-col gap-1.5 rounded-[12px] border border-line-2 pt-2.5 pr-2 pb-2 pl-3.5 opacity-60">
        <label className="flex">
          <span className="sr-only">{t("shell.chat.message")}</span>
          <textarea
            disabled
            rows={2}
            placeholder={t("shell.chat.placeholder")}
            className="flex-1 resize-none border-0 bg-transparent text-13 text-text outline-none placeholder:text-ghost"
          />
        </label>
        <div className="flex items-center justify-between text-12 text-text-3">
          <span>{t("shell.chat.shortcut")}</span>
          <button
            type="button"
            disabled
            aria-label={t("shell.chat.send")}
            className="inline-flex size-[26px] items-center justify-center rounded-[6px] border-0 bg-muted text-text-3"
          >
            <Icon name="send" />
          </button>
        </div>
      </div>
    </aside>
  );
}
