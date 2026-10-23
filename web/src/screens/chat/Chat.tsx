import { useState, type ReactNode } from "react";
import { AiMark } from "../../app/AiMark";
import { useErrorText } from "../../app/errors";
import { useAcervoChat, useConversations, useThread, type ChatMessage } from "../../data/chat";
import { useKbs } from "../../data/kbs";
import { useAutoApplied, usePendingProposals } from "../../data/proposals";
import { useNode } from "../../data/tree";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { Dot } from "../../ui/Dot";
import { Icon } from "../../ui/Icon";
import { IconButton } from "../../ui/IconButton";
import { Menu, MenuItem } from "../../ui/Menu";
import { Composer, type PageRef } from "./Composer";
import { Conversations, DeleteConversation } from "./Conversations";
import { FollowProvider } from "./follow";
import { PendingList } from "./PendingList";
import { Thread } from "./Thread";

type View = "thread" | "pending" | "conversations";

type Box = {
  kbId: string;
  openPage: PageRef | null;
  files: File[];
  setFiles: (files: File[]) => void;
  onPosted: (conversationId: string) => void;
};

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

/** The open conversation over the AI SDK's chat: its thread, following a reply still working, and the box. */
function Live({ initial, working, conversationId, ...box }: Box & { initial: ChatMessage[]; working: string | null; conversationId: string | null }) {
  const errorText = useErrorText();
  const chat = useAcervoChat({ kbId: box.kbId, conversationId, initial, working, onPosted: box.onPosted });
  const busy = chat.status === "submitted" || chat.status === "streaming";
  return (
    <FollowProvider value={chat.follow}>
      <Thread kbId={box.kbId} messages={chat.messages} status={chat.status} streamFailed={chat.failed} />
      {chat.sendError != null && (
        <p role="alert" className="m-0 px-4 pb-2 text-12 text-err">
          {errorText(chat.sendError)}
        </p>
      )}
      <Composer kbId={box.kbId} openPage={box.openPage} files={box.files} setFiles={box.setFiles} sending={busy} onSend={chat.send} />
    </FollowProvider>
  );
}

/** A conversation as it was stored, loaded once when it opens; a new one starts empty. */
function Conversation({ conversationId, ...box }: Box & { conversationId: string | null }) {
  const errorText = useErrorText();
  const [opened] = useState(conversationId);
  const thread = useThread(opened);
  if (opened !== null && !thread.data)
    return (
      <div className="flex flex-1 flex-col justify-end px-4 py-3">
        {thread.isError && (
          <p role="alert" className="m-0 text-12 text-err">
            {errorText(thread.error)}
          </p>
        )}
      </div>
    );
  return <Live {...box} conversationId={opened} initial={thread.data?.messages ?? []} working={thread.data?.working ?? null} />;
}

/**
 * The one chat of a base, with no modes: the header (base, past conversations, new, the conversation's menu), what
 * waits in the base and what agents applied, the thread and the box.
 */
export function Chat({ kbId, nodeId, onClose }: { kbId: string; nodeId?: string; onClose: () => void }) {
  const { t } = useI18n();
  const kb = useKbs().data?.find((candidate) => candidate.id === kbId);
  const listed = useConversations(kbId);
  const conversations = listed.data ?? [];
  // undefined: the most recent conversation; null: a new one, started by the first message.
  const [chosen, setChosen] = useState<string | null | undefined>(undefined);
  // Each open is a new session; a conversation the first message started keeps the session it started in.
  const [session, setSession] = useState(0);
  const [started, setStarted] = useState<string | null>(null);
  const conversationId = chosen === undefined ? (conversations[0]?.id ?? null) : chosen;
  const current = conversations.find((conversation) => conversation.id === conversationId);
  const pending = usePendingProposals(kbId).data ?? [];
  const applied = useAutoApplied(kbId).data ?? [];
  const [view, setView] = useState<View>("thread");
  const [deleting, setDeleting] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);

  const node = useNode(nodeId ?? "", Boolean(nodeId)).data;
  const openPage: PageRef | null = node?.kind === "page" ? { id: node.id, title: node.title } : null;

  const switchTo = (id: string | null) => {
    setChosen(id);
    setStarted(null);
    setSession((n) => n + 1);
  };
  const open = (id: string | null) => {
    switchTo(id);
    setView("thread");
  };
  const deleted = (id: string) => {
    if (id === conversationId) switchTo(null);
  };
  const posted = (id: string) => {
    if (conversationId === null) setStarted(id);
    setChosen(id);
  };

  const ready = chosen !== undefined || !listed.isPending;
  const threadKey = `${session}:${conversationId === null || conversationId === started ? "new" : conversationId}`;

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
          {current && (
            <Menu
              align="end"
              label={t("chat.menu")}
              trigger={
                <IconButton aria-label={t("chat.menu")}>
                  <Icon name="more" size={15} />
                </IconButton>
              }
            >
              <MenuItem onSelect={() => setDeleting(true)}>{t("chat.delete")}</MenuItem>
            </Menu>
          )}
          <IconButton aria-label={t("shell.chat.close")} onClick={onClose}>
            <Icon name="close" size={15} />
          </IconButton>
        </span>
      </div>

      {view === "thread" && pending.length + applied.length > 0 && (
        <div className="flex items-center justify-between gap-2 border-b border-line py-2 pr-3 pl-4">
          {pending.length > 0 ? (
            <Dot tone="warn">
              {pending.length === 1 ? t("chat.pending.count.one") : t("chat.pending.count.other", { count: pending.length })}
            </Dot>
          ) : (
            <Dot tone="ok">
              {applied.length === 1 ? t("chat.applied.count.one") : t("chat.applied.count.other", { count: applied.length })}
            </Dot>
          )}
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
          <PendingList proposals={pending} applied={applied} onOpenConversation={open} />
        </>
      )}
      {view === "conversations" && (
        <>
          <History title={t("chat.conversations")} onBack={() => setView("thread")} />
          <Conversations kbId={kbId} conversations={conversations} current={conversationId} onOpen={open} onDeleted={deleted} />
        </>
      )}
      {/* Hidden, not unmounted, so a reply keeps streaming while the lists are open. */}
      <div hidden={view !== "thread"} className="contents">
        {ready && (
          <Conversation
            key={threadKey}
            kbId={kbId}
            conversationId={conversationId}
            openPage={openPage}
            files={files}
            setFiles={setFiles}
            onPosted={posted}
          />
        )}
      </div>
      {deleting && current && (
        <DeleteConversation kbId={kbId} conversation={current} onClose={() => setDeleting(false)} onDeleted={deleted} />
      )}
      {dragging && (
        <div className="pointer-events-none absolute inset-2 flex items-center justify-center rounded-[12px] border border-dashed border-ink bg-bg/90 text-text-2">
          {t("chat.drop")}
        </div>
      )}
    </div>
  );
}
