import { useI18n } from "../i18n";
import { Button } from "./Button";
import { Icon, type IconName } from "./Icon";
import { cx } from "./cx";

export type MediaTool = "caption" | "replace" | "download" | "open";

const icons: Record<MediaTool, IconName> = { caption: "page", replace: "upload", download: "download", open: "expand" };

/**
 * The actions of an image or a video. `floating` pins it to the top-right of its parent, which must be `relative group`,
 * and shows it only while the parent is hovered or holds the focus.
 */
export function MediaToolbar({
  tools,
  floating = false,
  onAction,
}: {
  tools: MediaTool[];
  floating?: boolean;
  onAction: (tool: MediaTool) => void;
}) {
  const { t } = useI18n();
  return (
    <div
      role="toolbar"
      aria-label={t("media.toolbar")}
      onKeyDown={(event) => {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        const buttons = Array.from(event.currentTarget.querySelectorAll("button"));
        const at = buttons.indexOf(event.target as HTMLButtonElement);
        const step = event.key === "ArrowRight" ? 1 : -1;
        buttons[(at + step + buttons.length) % buttons.length]?.focus();
      }}
      className={cx(
        "inline-flex gap-0.5 rounded-[8px] border border-line-2 bg-bg p-0.5",
        floating && "absolute top-2 right-2 opacity-0 group-focus-within:opacity-100 group-hover:opacity-100",
      )}
    >
      {tools.map((tool) => (
        <Button key={tool} variant="quiet" size="sm" icon aria-label={t(`media.tool.${tool}`)} onClick={() => onAction(tool)}>
          <Icon name={icons[tool]} size={14} />
        </Button>
      ))}
    </div>
  );
}
