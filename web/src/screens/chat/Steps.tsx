import { getToolName, isToolUIPart } from "ai";
import type { ChatPart } from "../../data/chat";
import { useI18n } from "../../i18n";
import { Dot } from "../../ui/Dot";

const TOOLS = ["list_folder", "read_page", "read_pdf_pages", "file_fact", "file_attachment", "move", "rename", "undo_last"];

type ToolPart = Extract<ChatPart, { toolCallId: string }>;

/** What the step was about: the path it read, the text it filed, the file it saved. */
function detailOf(part: ToolPart): string | null {
  const input = (part.input ?? {}) as Record<string, unknown>;
  const output = (part.state === "output-available" ? part.output : null) as Record<string, unknown> | null;
  const detail = input.path ?? output?.path ?? input.name ?? input.title ?? input.text;
  return typeof detail === "string" && detail ? detail : null;
}

/** The base's tools a reply used, as they ran: done, running or failed. */
export function Steps({ parts }: { parts: ChatPart[] }) {
  const { t } = useI18n();
  const steps = parts.filter(isToolUIPart) as ToolPart[];
  if (steps.length === 0) return null;
  return (
    <ol aria-label={t("chat.steps")} className="m-0 flex list-none flex-col p-0">
      {steps.map((part) => {
        const name = getToolName(part);
        const done = part.state === "output-available";
        const failed = part.state === "output-error";
        const detail = detailOf(part);
        return (
          // The label keeps its width; a long detail (a whole fact) truncates in what is left instead of covering it.
          <li key={part.toolCallId} className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-2 text-12 leading-[22px] text-text-3">
            <Dot tone={failed ? "err" : done ? "ok" : "run"}>
              <span className={`whitespace-nowrap ${done ? "text-text-3" : "text-text"}`}>
                {t(TOOLS.includes(name) ? `chat.step.${name}` : "chat.step.other")}
              </span>
            </Dot>
            {detail && <span className="truncate font-mono text-text-2">{detail}</span>}
          </li>
        );
      })}
    </ol>
  );
}
