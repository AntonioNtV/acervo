import { useI18n } from "../i18n";
import { Button } from "../ui/Button";
import { TextTabs } from "../ui/TextTabs";
import { AiMark } from "./AiMark";

/** The chat arrives in F2; until then the column only holds its place, everything disabled. */
export function ChatColumn() {
  const { t } = useI18n();
  return (
    <aside
      aria-label={t("app.chat.label")}
      className="flex w-[360px] max-w-[400px] min-w-0 shrink-0 flex-col border-l border-line bg-bg xl:w-[400px]"
    >
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-line pr-3 pl-[18px]">
        <span className="flex items-center gap-2 font-medium">
          <AiMark />
          {t("app.chat.label")}
        </span>
        <TextTabs
          label={t("app.chat.mode")}
          value="capture"
          onChange={() => {}}
          disabled
          options={[
            { value: "capture", label: t("app.chat.capture") },
            { value: "ask", label: t("app.chat.ask") },
          ]}
        />
      </div>
      <div className="flex flex-1 items-center justify-center p-5 text-text-3">{t("app.chat.soon")}</div>
      <div className="m-3 flex flex-col gap-1.5 rounded-[12px] border border-line-2 pt-2.5 pr-2 pb-2 pl-3.5">
        <label className="flex">
          <span className="sr-only">{t("app.chat.message")}</span>
          <textarea
            disabled
            rows={2}
            placeholder={t("app.chat.placeholder")}
            className="flex-1 resize-none border-0 bg-transparent text-13 text-text outline-none placeholder:text-ghost"
          />
        </label>
        <div className="flex items-center justify-between">
          <Button variant="quiet" size="sm" icon disabled aria-label={t("app.chat.attach")}>
            <svg viewBox="0 0 24 24" width={15} height={15} aria-hidden="true" className="fill-none stroke-current stroke-[1.5]">
              <path d="m21 11-8.5 8.5a5 5 0 0 1-7-7L14 4a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L15 7" />
            </svg>
          </Button>
          <Button variant="ink" size="sm" icon disabled aria-label={t("app.chat.send")}>
            <svg viewBox="0 0 24 24" width={15} height={15} aria-hidden="true" className="fill-none stroke-current stroke-[1.5]">
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          </Button>
        </div>
      </div>
    </aside>
  );
}
