import { useCallback, useState, type ReactNode } from "react";
import { AiMark } from "../../app/AiMark";
import { useErrorText } from "../../app/errors";
import {
  useConversationEvents,
  useConversations,
  useMessages,
  useSendMessage,
  type ChatEvent,
  type StepEvent,
} from "../../data/chat";
import { useKbs } from "../../data/kbs";
import { usePendingProposals, useProposalStates, type Proposal, type ProposalSummary } from "../../data/proposals";
import { useNode } from "../../data/tree";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { Dot } from "../../ui/Dot";
import { Icon } from "../../ui/Icon";
import { IconButton } from "../../ui/IconButton";
import { Composer, type PageRef } from "./Composer";
import { Conversations } from "./Conversations";
import { PendingList } from "./PendingList";
import { Thread } from "./Thread";

type View = "thread" | "pending" | "conversations";

function History({ title, onBack }: { title: ReactNode; onBack: () => void }) {
  const { t } = useI18n();
  return (
    <div className="flex h-11 shrink-0 items-center justify-between border-b border-line pr-2 pl-4">
      <span className="font-medium">{title}</span>
      <Button size="sm" variant="quiet" onClick={onBack}>
        {t("chat.back")}
      </Button>
    </div>
  );
}

/**
 * The one chat of a base, with no modes: the header (base, past conversations, new), how many proposals wait in the
 * base, the thread and the box.
 */
export function Chat({ kbId, nodeId, onClose }: { kbId: string; nodeId?: string; onClose: () => void }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const kb = useKbs().data?.find((candidate) => candidate.id === kbId);
  const conversations = useConversations(kbId).data ?? [];
  // undefined: the most recent conversation; null: a new one, started by the first message.
  const [chosen, setChosen] = useState<string | null | undefined>(undefined);
  const conversationId = chosen === undefined ? (conversations[0]?.id ?? null) : chosen;
  const messages = useMessages(conversationId).data ?? [];
  const pending = usePendingProposals(kbId).data ?? [];
  const states = useProposalStates().data ?? {};
  const [view, setView] = useState<View>("thread");
  const [steps, setSteps] = useState<Record<string, StepEvent[]>>({});
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const send = useSendMessage(kbId);

  const node = useNode(nodeId ?? "", Boolean(nodeId)).data;
  const openPage: PageRef | null = node?.kind === "page" ? { id: node.id, title: node.title } : null;

  useConversationEvents(
    conversationId,
    useCallback((event: ChatEvent) => {
      if (event.type === "step")
        setSteps((current) => ({ ...current, [event.message_id]: [...(current[event.message_id] ?? []), event] }));
    }, []),
  );

  const proposalsOf = (replyId: string) => {
    // The card draws each one's newest state; this only finds them: listed as waiting, or seen in this session.
    const byId = new Map<string, Proposal | ProposalSummary>();
    for (const proposal of [...pending, ...Object.values(states)])
      if (proposal.message_id === replyId && !byId.has(proposal.id)) byId.set(proposal.id, proposal);
    return [...byId.values()].sort((a, b) => a.created_at.localeCompare(b.created_at));
  };

  const open = (id: string | null) => {
    setChosen(id);
    setView("thread");
  };

  return (
    <div
      className="relative flex min-h-0 flex-1 flex-col"
      onDragOver={(event) => {
        if (!event.dataTransfer.types.includes("Files")) return;
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false);
      }}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        setFiles([...files, ...Array.from(event.dataTransfer.files)]);
      }}
    >
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-line pr-1.5 pl-4">
        <span className="flex min-w-0 items-center gap-2 font-medium">
          <AiMark size={15} />
          {t("shell.chat.label")}
          {kb && <span className="truncate font-normal text-text-3">{t("chat.in", { name: kb.name })}</span>}
        </span>
        <span className="flex items-center gap-0.5">
          <IconButton aria-label={t("chat.conversations")} onClick={() => setView(view === "conversations" ? "thread" : "conversations")}>
            <Icon name="recent" size={15} />
          </IconButton>
          <IconButton aria-label={t("chat.new")} onClick={() => open(null)}>
            <Icon name="plus" size={15} />
          </IconButton>
          <IconButton aria-label={t("shell.chat.close")} onClick={onClose}>
            <Icon name="close" size={15} />
          </IconButton>
        </span>
      </div>

      {view === "thread" && pending.length > 0 && (
        <div className="flex items-center justify-between gap-2 border-b border-line py-2 pr-3 pl-4">
          <Dot tone="warn">
            {pending.length === 1 ? t("chat.pending.count.one") : t("chat.pending.count.other", { count: pending.length })}
          </Dot>
          <Button size="sm" variant="quiet" onClick={() => setView("pending")}>
            {t("chat.pending.open")}
          </Button>
        </div>
      )}

      {view === "pending" && (
        <>
          <History
            title={
              <>
                {t("chat.pending.title")} <span className="font-normal text-ghost">{pending.length}</span>
              </>
            }
            onBack={() => setView("thread")}
          />
          <PendingList proposals={pending} onOpenConversation={open} />
        </>
      )}
      {view === "conversations" && (
        <>
          <History title={t("chat.conversations")} onBack={() => setView("thread")} />
          <Conversations conversations={conversations} current={conversationId} onOpen={open} />
        </>
      )}
      {view === "thread" && (
        <>
          <Thread messages={messages} steps={steps} proposalsOf={proposalsOf} />
          {send.error && (
            <p role="alert" className="m-0 px-4 pb-2 text-12 text-err">
              {errorText(send.error)}
            </p>
          )}
          <Composer
            kbId={kbId}
            openPage={openPage}
            files={files}
            setFiles={setFiles}
            sending={send.isPending}
            onSend={(message) => send.mutateAsync({ conversationId, message }).then((id) => setChosen(id))}
          />
        </>
      )}
      {dragging && (
        <div className="pointer-events-none absolute inset-2 flex items-center justify-center rounded-[12px] border border-dashed border-ink bg-bg/90 text-text-2">
          {t("chat.drop")}
        </div>
      )}
    </div>
  );
}
