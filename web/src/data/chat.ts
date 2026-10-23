import { useChat } from "@ai-sdk/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ChatTransport, UIMessage, UIMessageChunk } from "ai";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, apiHeaders } from "../api/client";
import type { components, paths } from "../api/schema.gen";
import { settleProposal, type Proposal, type ProposalSummary } from "./proposals";
import { ApiError, call } from "./request";

type Schemas = components["schemas"];
export type Conversation = Schemas["ConversationRead"];
export type Message = Schemas["MessageRead"];
export type Citation = Schemas["Citation"];
export type Attachment = Schemas["Attachment"];

/** What the thread knows of a message besides its parts: a person's context, a reply's state. */
export type MessageMetadata = {
  status?: Message["status"];
  grounded?: boolean;
  selection?: string | null;
  attachments?: Pick<Attachment, "name" | "size">[];
};
export type ChatMessage = UIMessage<MessageMetadata, { proposal: Proposal | ProposalSummary }>;
export type ChatPart = ChatMessage["parts"][number];

// After a stream drops, so a restarting API is not asked in a loop.
const RECONNECT_MS = 2000;
const POST_MESSAGE ="/v1/conversations/{conversation_id}/messages" satisfies keyof paths;
const streamPath = (replyId: string) => `/v1/messages/${encodeURIComponent(replyId)}/stream`;
const uiMessagesPath = (conversationId: string) => `/v1/conversations/${encodeURIComponent(conversationId)}/ui-messages`;

/** The base's conversations with its built-in chat, the most recent first. */
export function useConversations(kbId: string | undefined) {
  return useQuery({
    queryKey: ["conversations", kbId ?? ""],
    enabled: Boolean(kbId),
    queryFn: () => call(api.GET("/v1/kbs/{kb_id}/conversations", { params: { path: { kb_id: kbId ?? "" } } })),
  });
}

export type Outgoing = {
  text: string;
  files: File[];
  pageId: string | null;
  selection: string | null;
};

/** A multipart POST with repeated `files` fields; XMLHttpRequest like the uploads, so both send files the same way. */
function sendForm<T>(path: string, form: FormData) {
  return new Promise<T>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", path);
    for (const [name, value] of Object.entries(apiHeaders)) request.setRequestHeader(name, value);
    request.responseType = "json";
    request.onload = () => {
      if (request.status >= 200 && request.status < 300) return resolve(request.response as T);
      reject(new ApiError(request.status, request.response, request.statusText));
    };
    request.onerror = () => reject(new ApiError(0, null, "network error"));
    request.send(form);
  });
}

// Plain fetch for the routes the generated client does not have yet.
async function fetchOk(path: string, signal?: AbortSignal): Promise<Response> {
  const response = await fetch(path, { headers: apiHeaders, signal });
  if (!response.ok) throw new ApiError(response.status, await response.json().catch(() => null), response.statusText);
  return response;
}

/** An SSE body of the AI SDK's UI message stream, as its chunks; `[DONE]` ends it. */
function chunksOf(body: ReadableStream<Uint8Array>): ReadableStream<UIMessageChunk> {
  const decoder = new TextDecoder();
  let buffer = "";
  return body.pipeThrough(
    new TransformStream<Uint8Array, UIMessageChunk>({
      transform(bytes, controller) {
        buffer += decoder.decode(bytes, { stream: true }).replace(/\r\n/g, "\n");
        let end: number;
        while ((end = buffer.indexOf("\n\n")) >= 0) {
          const data = buffer
            .slice(0, end)
            .split("\n")
            .filter((line) => line.startsWith("data:"))
            .map((line) => line.slice(5).trimStart())
            .join("\n");
          buffer = buffer.slice(end + 2);
          if (data && data !== "[DONE]") controller.enqueue(JSON.parse(data) as UIMessageChunk);
        }
      },
    }),
  );
}

/** A reply's stream from its start: what it already wrote, then live until it ends. */
async function replyStream(replyId: string, signal?: AbortSignal) {
  const response = await fetchOk(streamPath(replyId), signal);
  if (!response.body) throw new ApiError(0, null, "empty stream");
  return chunksOf(response.body);
}

function personMessage(message: Message): ChatMessage {
  return {
    id: message.id,
    role: "user",
    metadata: { selection: message.context?.selection, attachments: message.attachments },
    parts: message.text ? [{ type: "text", text: message.text }] : [],
  };
}

/**
 * The stored thread as UI messages, each reply with its state, and the reply still working, if any. The working one
 * is left out: following its stream replays it from the start.
 */
export function useThread(conversationId: string | null) {
  return useQuery({
    queryKey: ["thread", conversationId ?? ""],
    enabled: conversationId !== null,
    gcTime: 0,
    queryFn: async () => {
      const id = conversationId ?? "";
      const [ui, stored] = await Promise.all([
        fetchOk(uiMessagesPath(id)).then((response) => response.json() as Promise<ChatMessage[]>),
        call(api.GET("/v1/conversations/{conversation_id}/messages", { params: { path: { conversation_id: id } } })),
      ]);
      const parts = new Map(ui.map((message) => [message.id, message.parts]));
      const working = [...stored].reverse().find((message) => message.role === "acervo" && message.status === "working")?.id ?? null;
      // A reply that was retried is not shown: the reply that replaced it is.
      const replaced = new Set(stored.map((message) => message.replaces_id));
      const messages = stored
        .filter((message) => message.id !== working && !replaced.has(message.id))
        .map((message): ChatMessage =>
          message.role === "person"
            ? personMessage(message)
            : {
                id: message.id,
                role: "assistant",
                metadata: { status: message.status, grounded: message.grounded },
                parts: parts.get(message.id) ?? (message.text ? [{ type: "text", text: message.text }] : []),
              },
        );
      return { messages, working };
    },
  });
}

type Sending = { message: Outgoing; userId?: string; posted: (error?: unknown) => void };

/**
 * One conversation over the AI SDK's chat. A message is posted (with its files and context) and its reply's stream
 * followed; a reply still working when the thread opened, a retry's or a redo's new reply, is followed the same way.
 * `onPosted` gets the conversation, started by the first message when there was none.
 */
export function useAcervoChat({
  kbId,
  conversationId,
  initial,
  working,
  onPosted,
}: {
  kbId: string;
  conversationId: string | null;
  initial: ChatMessage[];
  working: string | null;
  onPosted: (conversationId: string) => void;
}) {
  const queryClient = useQueryClient();
  const conversation = useRef(conversationId);
  const following = useRef(working);
  const sending = useRef<Sending | null>(null);
  const posted = useRef(onPosted);
  posted.current = onPosted;
  const [sendError, setSendError] = useState<unknown>(null);
  const [dropped, setDropped] = useState(false);

  const transport = useMemo<ChatTransport<ChatMessage>>(
    () => ({
      sendMessages: async ({ messages, abortSignal }) => {
        const current = sending.current;
        if (!current) throw new Error("nothing to send");
        current.userId = messages.at(-1)?.id;
        try {
          conversation.current ??= (
            await call(api.POST("/v1/kbs/{kb_id}/conversations", { params: { path: { kb_id: kbId } }, body: { title: "" } }))
          ).id;
          const { message } = current;
          const form = new FormData();
          form.append("text", message.text);
          for (const file of message.files) form.append("files", file);
          if (message.pageId) form.append("page_id", message.pageId);
          if (message.selection) form.append("selection", message.selection);
          const { reply } = await sendForm<Schemas["MessagePosted"]>(
            POST_MESSAGE.replace("{conversation_id}", encodeURIComponent(conversation.current)),
            form,
          );
          following.current = reply.id;
          current.posted();
          posted.current(conversation.current);
          void queryClient.invalidateQueries({ queryKey: ["conversations", kbId] });
          return await replyStream(reply.id, abortSignal);
        } catch (error) {
          current.posted(error);
          throw error;
        }
      },
      reconnectToStream: async ({ abortSignal }) => (following.current ? replyStream(following.current, abortSignal) : null),
    }),
    [kbId, queryClient],
  );

  const reconnect = useRef<(partialId: string) => void>(() => {});
  const chat = useChat<ChatMessage>({
    messages: initial,
    transport,
    resume: working !== null,
    onData: (part) => {
      if (part.type === "data-proposal" && "payload" in part.data) void settleProposal(queryClient, part.data);
    },
    // A dropped connection is not a failed reply: its job runs on, so its stream is read again from the start.
    onFinish: ({ message, isDisconnect }) => {
      if (!isDisconnect) return;
      setDropped(true);
      reconnect.current(message.id);
    },
  });
  const { setMessages, resumeStream, stop } = chat;

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    reconnect.current = (partialId) => {
      timer = setTimeout(() => {
        // The SDK keeps a dropped reply as it was and would add the replay from `start` to it. The partial reply
        // leaves the thread, and a resume with nothing to follow drops what the SDK kept, so the replay builds it once.
        const replyId = following.current;
        setMessages((messages) => messages.filter((m) => m.id !== partialId));
        following.current = null;
        void resumeStream().then(() => {
          setDropped(false);
          following.current = replyId;
          return resumeStream();
        });
      }, RECONNECT_MS);
    };
    return () => {
      clearTimeout(timer);
      void stop();
    };
  }, [resumeStream, setMessages, stop]);

  /** Resolves once the message is stored (the box empties); the reply streams on. */
  const send = (message: Outgoing) =>
    new Promise<void>((resolve, reject) => {
      setSendError(null);
      const current: Sending = {
        message,
        posted: (error) => {
          if (error === undefined) return resolve();
          // The text stays in the box to send again, so the message leaves the thread.
          setMessages((messages) => messages.filter((m) => m.id !== current.userId));
          setSendError(error);
          reject(error);
        },
      };
      sending.current = current;
      void chat.sendMessage({
        text: message.text,
        metadata: { selection: message.selection, attachments: message.files.map(({ name, size }) => ({ name, size })) },
      });
    });

  /** Follows a new reply's stream in the thread, in place of the reply it replaces. */
  const follow = (replyId: string, replaces?: string) => {
    following.current = replyId;
    if (replaces) setMessages((messages) => messages.filter((m) => m.id !== replaces));
    void resumeStream();
  };

  // A reply failed when its stream said so, not when the message never got posted or the connection dropped.
  const failed = chat.status === "error" && sendError === null && !dropped;
  return { messages: chat.messages, status: chat.status, failed, sendError, send, follow };
}

/** "Tentar de novo": a new reply running the message again. */
export function useRetry() {
  return useMutation({
    mutationFn: (replyId: string) =>
      call(api.POST("/v1/messages/{message_id}/retry", { params: { path: { message_id: replyId } } })),
  });
}

/** "Refazer" on a stale proposal: its message runs again into a new reply, on the page's newest text. */
export function useRedo() {
  return useMutation({
    mutationFn: (proposalId: string) =>
      call(api.POST("/v1/proposals/{proposal_id}/redo", { params: { path: { proposal_id: proposalId } } })),
  });
}

/** "Apagar conversa": it leaves the list; what it proposed stays. */
export function useDeleteConversation(kbId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (conversationId: string) =>
      call(api.DELETE("/v1/conversations/{conversation_id}", { params: { path: { conversation_id: conversationId } } })),
    onSuccess: (_, conversationId) => {
      queryClient.setQueryData<Conversation[]>(["conversations", kbId], (list = []) =>
        list.filter((conversation) => conversation.id !== conversationId),
      );
      return queryClient.invalidateQueries({ queryKey: ["conversations", kbId] });
    },
  });
}
