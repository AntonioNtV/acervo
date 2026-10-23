import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api, apiHeaders } from "../api/client";
import type { components, paths } from "../api/schema.gen";
import { settleProposal } from "./proposals";
import { ApiError, call } from "./request";

type Schemas = components["schemas"];
export type Conversation = Schemas["ConversationRead"];
export type Message = Schemas["MessageRead"];
export type Route = Schemas["Reroute"]["route"];
export type StepEvent = Schemas["StepEvent"];
export type ChatEvent =
  | Schemas["StepEvent"]
  | Schemas["ProposalEvent"]
  | Schemas["MessageEvent"]
  | Schemas["DoneEvent"]
  | Schemas["ErrorEvent"];

export const ROUTES: Route[] = ["guardar", "perguntar", "organizar", "conversar"];

const POST_MESSAGE = "/v1/conversations/{conversation_id}/messages" satisfies keyof paths;
// After the stream ends or drops, so a restarting API is not asked in a loop.
const RECONNECT_MS = 2000;

/** The base's conversations with its built-in chat, the most recent first. */
export function useConversations(kbId: string | undefined) {
  return useQuery({
    queryKey: ["conversations", kbId ?? ""],
    enabled: Boolean(kbId),
    queryFn: () => call(api.GET("/v1/kbs/{kb_id}/conversations", { params: { path: { kb_id: kbId ?? "" } } })),
  });
}

export function useMessages(conversationId: string | null) {
  return useQuery({
    queryKey: ["messages", conversationId ?? ""],
    enabled: conversationId !== null,
    queryFn: () =>
      call(
        api.GET("/v1/conversations/{conversation_id}/messages", {
          params: { path: { conversation_id: conversationId ?? "" } },
        }),
      ),
  });
}

/** A message stored or changed: put in its place in the conversation, or at its end. */
function upsertMessage(queryClient: QueryClient, message: Message) {
  queryClient.setQueryData<Message[]>(["messages", message.conversation_id], (messages = []) =>
    messages.some((m) => m.id === message.id)
      ? messages.map((m) => (m.id === message.id ? message : m))
      : [...messages, message],
  );
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

/** Starts a conversation when there is none yet, then posts; resolves to the conversation it went to. */
export function useSendMessage(kbId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ conversationId, message }: { conversationId: string | null; message: Outgoing }) => {
      const id =
        conversationId ??
        (await call(api.POST("/v1/kbs/{kb_id}/conversations", { params: { path: { kb_id: kbId } }, body: { title: "" } })))
          .id;
      const form = new FormData();
      form.append("text", message.text);
      for (const file of message.files) form.append("files", file);
      if (message.pageId) form.append("page_id", message.pageId);
      if (message.selection) form.append("selection", message.selection);
      const posted = await sendForm<Schemas["MessagePosted"]>(
        POST_MESSAGE.replace("{conversation_id}", encodeURIComponent(id)),
        form,
      );
      upsertMessage(queryClient, posted.message);
      upsertMessage(queryClient, posted.reply);
      return id;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["conversations", kbId] }),
  });
}

/** "Mudar", an ask-first choice or "Tentar de novo": a new reply redoing the message as `route`. */
export function useReroute() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ replyId, route }: { replyId: string; route: Route }) =>
      call(api.POST("/v1/messages/{message_id}/reroute", { params: { path: { message_id: replyId } }, body: { route } })),
    onSuccess: (reply) => upsertMessage(queryClient, reply),
  });
}

/** Each `data:` line of an SSE body, as its JSON. */
async function* readEvents(body: ReadableStream<Uint8Array>): AsyncGenerator<ChatEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let end: number;
    while ((end = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const data = block
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      if (data) yield JSON.parse(data) as ChatEvent;
    }
  }
}

/**
 * The conversation's live events, read with fetch since an `EventSource` cannot send the key. Messages and proposals
 * go into the cache; `onEvent` sees every event (the thread keeps the steps). Each (re)connection rereads the messages,
 * so what happened while it was away is not lost.
 */
export function useConversationEvents(conversationId: string | null, onEvent: (event: ChatEvent) => void) {
  const queryClient = useQueryClient();
  const latest = useRef(onEvent);
  latest.current = onEvent;

  useEffect(() => {
    if (!conversationId) return;
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;

    const handle = (event: ChatEvent) => {
      if (event.type === "message") upsertMessage(queryClient, event.message);
      if (event.type === "proposal") void settleProposal(queryClient, event.proposal);
      if (event.type === "done" || event.type === "error")
        void queryClient.invalidateQueries({ queryKey: ["messages", conversationId] });
      latest.current(event);
    };

    const connect = async () => {
      try {
        const { data, response } = await api.GET("/v1/conversations/{conversation_id}/events", {
          params: { path: { conversation_id: conversationId } },
          parseAs: "stream",
          signal: abort.signal,
        });
        if (response.ok && data) {
          void queryClient.invalidateQueries({ queryKey: ["messages", conversationId] });
          for await (const event of readEvents(data)) handle(event);
        }
      } catch {
        // Dropped or aborted; reconnecting below unless it was aborted.
      }
      if (!abort.signal.aborted) timer = setTimeout(connect, RECONNECT_MS);
    };
    void connect();
    return () => {
      abort.abort();
      clearTimeout(timer);
    };
  }, [conversationId, queryClient]);
}
