import { useState } from "react";
import { useErrorText } from "../../app/errors";
import { useDeleteConversation, type Conversation } from "../../data/chat";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { cx } from "../../ui/cx";
import { Dialog, DialogClose } from "../../ui/Dialog";
import { Icon } from "../../ui/Icon";
import { IconButton } from "../../ui/IconButton";
import { formatDate } from "../file/format";

/** "Apagar conversa", confirmed first; what it proposed stays. */
export function DeleteConversation({
  kbId,
  conversation,
  onClose,
  onDeleted,
}: {
  kbId: string;
  conversation: Conversation;
  onClose: () => void;
  onDeleted: (conversationId: string) => void;
}) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const remove = useDeleteConversation(kbId);
  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={t("chat.delete.title", { name: conversation.title || t("chat.conversations.untitled") })}
      description={t("chat.delete.text")}
      footer={
        <>
          <DialogClose asChild>
            <Button variant="quiet">{t("chat.cancel")}</Button>
          </DialogClose>
          <Button
            variant="ink"
            disabled={remove.isPending}
            onClick={() =>
              remove.mutate(conversation.id, {
                onSuccess: () => {
                  onDeleted(conversation.id);
                  onClose();
                },
              })
            }
          >
            {t("chat.delete")}
          </Button>
        </>
      }
    >
      {remove.error && (
        <p role="alert" className="m-0 text-12 text-err">
          {errorText(remove.error, { conflict: t("chat.delete.working") })}
        </p>
      )}
    </Dialog>
  );
}

/** The base's past conversations, the most recent first, to reopen or delete. */
export function Conversations({
  kbId,
  conversations,
  current,
  onOpen,
  onDeleted,
}: {
  kbId: string;
  conversations: Conversation[];
  current: string | null;
  onOpen: (conversationId: string) => void;
  onDeleted: (conversationId: string) => void;
}) {
  const { t, lang } = useI18n();
  const [deleting, setDeleting] = useState<Conversation | null>(null);
  if (conversations.length === 0) return <p className="m-0 px-4 py-6 text-text-3">{t("chat.conversations.none")}</p>;
  return (
    <>
      <ul aria-label={t("chat.conversations")} className="m-0 flex min-h-0 flex-1 list-none flex-col overflow-y-auto p-0">
        {conversations.map((conversation) => {
          const title = conversation.title || t("chat.conversations.untitled");
          return (
            <li
              key={conversation.id}
              className={cx("flex items-center border-b border-line pr-2 hover:bg-side", conversation.id === current && "bg-subtle")}
            >
              <button
                type="button"
                aria-current={conversation.id === current ? "true" : undefined}
                onClick={() => onOpen(conversation.id)}
                className="flex min-w-0 flex-1 cursor-pointer flex-col gap-0.5 border-0 bg-transparent px-4 py-3 text-left font-[inherit] text-13 text-text"
              >
                <span className="truncate font-medium">{title}</span>
                <span className="text-12 text-text-3">{formatDate(conversation.updated_at, lang)}</span>
              </button>
              <IconButton aria-label={t("chat.delete.of", { name: title })} onClick={() => setDeleting(conversation)}>
                <Icon name="trash" size={15} />
              </IconButton>
            </li>
          );
        })}
      </ul>
      {deleting && (
        <DeleteConversation kbId={kbId} conversation={deleting} onClose={() => setDeleting(null)} onDeleted={onDeleted} />
      )}
    </>
  );
}
