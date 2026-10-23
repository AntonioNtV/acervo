import type { Conversation } from "../../data/chat";
import { useI18n } from "../../i18n";
import { cx } from "../../ui/cx";
import { formatDate } from "../file/format";

/** The base's past conversations, the most recent first, to reopen. */
export function Conversations({
  conversations,
  current,
  onOpen,
}: {
  conversations: Conversation[];
  current: string | null;
  onOpen: (conversationId: string) => void;
}) {
  const { t, lang } = useI18n();
  if (conversations.length === 0) return <p className="m-0 px-4 py-6 text-text-3">{t("chat.conversations.none")}</p>;
  return (
    <ul aria-label={t("chat.conversations")} className="m-0 flex min-h-0 flex-1 list-none flex-col overflow-y-auto p-0">
      {conversations.map((conversation) => (
        <li key={conversation.id} className="border-b border-line">
          <button
            type="button"
            aria-current={conversation.id === current ? "true" : undefined}
            onClick={() => onOpen(conversation.id)}
            className={cx(
              "flex w-full cursor-pointer flex-col gap-0.5 border-0 bg-transparent px-4 py-3 text-left font-[inherit] text-13 text-text hover:bg-side",
              conversation.id === current && "bg-subtle",
            )}
          >
            <span className="truncate font-medium">{conversation.title || t("chat.conversations.untitled")}</span>
            <span className="text-12 text-text-3">{formatDate(conversation.updated_at, lang)}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
