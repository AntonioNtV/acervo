import "@testing-library/jest-dom/vitest";
import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { apiFetch, calls, node, renderWithApi, resetApi, respond } from "../../api/testing";
import { Chat } from "./Chat";
import { append, message, proposal, T0, undo } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

const editor = vi.hoisted(() => ({ selection: "" }));
vi.mock("../../editor/BlockEditor", () => ({ useEditorSelection: () => editor.selection }));

class FakeXhr {
  static sent: FakeXhr[] = [];
  onload?: () => void;
  status = 0;
  statusText = "";
  response: unknown = null;
  responseType = "";
  form?: FormData;
  path = "";
  open(_method: string, path: string) {
    this.path = path;
  }
  setRequestHeader() {}
  send(form: FormData) {
    this.form = form;
    FakeXhr.sent.push(this);
  }
  reply(status: number, body: unknown) {
    this.status = status;
    this.response = body;
    this.onload?.();
  }
}

const conversation = (id: string, title: string) => ({ id, kb_id: "kb-1", agent_id: "agent-chat", title, created_at: T0, updated_at: T0 });
const lines = (chunks: unknown[]) => chunks.map((chunk) => `data: ${JSON.stringify(chunk)}\n\n`).join("");
/** A reply that ended: all its chunks, then `[DONE]`. */
const ended = (...chunks: unknown[]) => () => ({ body: lines([...chunks, { type: "finish" }]) + "data: [DONE]\n\n" });
/** A reply still working: its chunks so far, and the stream stays open. */
const working = (...chunks: unknown[]) => () => ({
  body: new ReadableStream({ start: (stream) => stream.enqueue(new TextEncoder().encode(lines(chunks))) }),
});
const text = (id: string, delta: string) => [
  { type: "text-start", id },
  { type: "text-delta", id, delta },
  { type: "text-end", id },
];
const person = (id: string, value: string, conversationId = "c-1") =>
  message(id, { role: "person", text: value, conversation_id: conversationId });

/** The stored thread: the messages, and their UI parts by id. */
function thread(conversationId: string, stored: ReturnType<typeof message>[], ui: unknown[] = []) {
  respond("GET", `/v1/conversations/${conversationId}/messages`, { body: stored });
  respond("GET", `/v1/conversations/${conversationId}/ui-messages`, { body: ui });
}

let conversations = [conversation("c-1", "Prazos"), conversation("c-2", "Vistorias")];

beforeEach(() => {
  resetApi();
  editor.selection = "";
  FakeXhr.sent = [];
  conversations = [conversation("c-1", "Prazos"), conversation("c-2", "Vistorias")];
  vi.stubGlobal("XMLHttpRequest", FakeXhr);
  vi.stubGlobal("fetch", apiFetch);
  respond("GET", "/v1/kbs", { body: [{ id: "kb-1", name: "Seguros · Operação" }] });
  respond("GET", "/v1/kbs/kb-1/conversations", () => ({ body: conversations }));
  thread("c-1", []);
  respond("GET", "/v1/kbs/kb-1/proposals", { body: [] });
  respond("GET", "/v1/nodes/page-1", {
    body: { ...node("page-1", "page", "Renovação e prazos"), path: "Bradesco/Renovação e prazos", page: null, file: null, versions: 0 },
  });
});

afterEach(() => vi.unstubAllGlobals());

function renderChat() {
  return renderWithApi(
    <MemoryRouter>
      <Chat kbId="kb-1" nodeId="page-1" onClose={() => {}} />
    </MemoryRouter>,
  );
}

const box = () => screen.getByRole("textbox", { name: "Mensagem" });
const streamed = (replyId: string) => calls.filter((call) => call.path === `/v1/messages/${replyId}/stream`);

describe("Chat", () => {
  it("has one box and no mode tabs", async () => {
    renderChat();
    expect(await screen.findByText("em Seguros · Operação")).toBeInTheDocument();
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
    expect(screen.queryByText("Capturar")).not.toBeInTheDocument();
    expect(screen.queryByText("Perguntar")).not.toBeInTheDocument();
  });

  it("sending posts the text with the open page and the selection, and the reply streams in as Markdown", async () => {
    respond("GET", "/v1/messages/r-1/stream", working({ type: "start", messageId: "r-1" }, ...text("t-1", "Guardo até **60 dias**.")));
    editor.selection = "Renovação aceita até 60 dias após o vencimento.";
    renderChat();
    expect(await screen.findByText("Renovação e prazos")).toBeInTheDocument();
    expect(screen.getByText("“Renovação aceita até 60 dias após o vencimento.”")).toBeInTheDocument();

    await userEvent.type(box(), "Isso também vale para o Auto.{Shift>}{Enter}{/Shift}Guarda lá.{Enter}");

    await waitFor(() => expect(FakeXhr.sent).toHaveLength(1));
    const [sent] = FakeXhr.sent as [FakeXhr];
    expect(sent.path).toBe("/v1/conversations/c-1/messages");
    expect(sent.form?.get("text")).toBe("Isso também vale para o Auto.\nGuarda lá.");
    expect(sent.form?.get("page_id")).toBe("page-1");
    expect(sent.form?.get("selection")).toBe("Renovação aceita até 60 dias após o vencimento.");
    expect(await screen.findByText("Trabalhando nisso…")).toBeInTheDocument();

    sent.reply(201, {
      message: person("m-1", "Isso também vale para o Auto.\nGuarda lá."),
      reply: message("r-1", { status: "working" }),
    });
    expect((await screen.findByText("60 dias")).tagName).toBe("STRONG");
    expect(box()).toHaveValue("");
    expect(streamed("r-1")[0]?.key).toBe("test-key");
  });

  it("the page and the selection chips can be removed before sending", async () => {
    editor.selection = "um trecho";
    renderChat();
    await userEvent.click(await screen.findByRole("button", { name: "Tirar a página do contexto" }));
    await userEvent.click(screen.getByRole("button", { name: "Tirar o trecho do contexto" }));
    await userEvent.type(box(), "Um fato.{Enter}");

    await waitFor(() => expect(FakeXhr.sent).toHaveLength(1));
    expect(FakeXhr.sent[0]?.form?.get("page_id")).toBeNull();
    expect(FakeXhr.sent[0]?.form?.get("selection")).toBeNull();
  });

  it("files attach to the message", async () => {
    renderChat();
    const file = new File(["%PDF"], "CG_Residencial_2026.pdf", { type: "application/pdf" });
    await userEvent.upload(await screen.findByLabelText("Arquivos para anexar"), file);
    expect(screen.getByRole("button", { name: "Tirar CG_Residencial_2026.pdf" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    await waitFor(() => expect(FakeXhr.sent).toHaveLength(1));
    expect(FakeXhr.sent[0]?.form?.getAll("files")).toEqual([file]);
  });

  it("a new conversation starts with the first message", async () => {
    respond("POST", "/v1/kbs/kb-1/conversations", { status: 201, body: conversation("c-3", "") });
    renderChat();
    await userEvent.click(screen.getByRole("button", { name: "Nova conversa" }));
    await userEvent.type(await screen.findByRole("textbox", { name: "Mensagem" }), "Um fato.{Enter}");

    await waitFor(() => expect(FakeXhr.sent[0]?.path).toBe("/v1/conversations/c-3/messages"));
  });

  it("a reply still working is followed: its steps show live", async () => {
    thread("c-1", [person("m-1", "Guarda este PDF."), message("r-1", { status: "working" })]);
    respond(
      "GET",
      "/v1/messages/r-1/stream",
      working(
        { type: "start", messageId: "r-1" },
        { type: "tool-input-available", toolCallId: "call-1", toolName: "file_attachment", input: { name: "CG_Residencial_2026.pdf" } },
      ),
    );
    renderChat();

    const steps = await screen.findByRole("list", { name: "Passos" });
    expect(steps).toHaveTextContent("procurando onde salvar");
    expect(steps).toHaveTextContent("CG_Residencial_2026.pdf");
    expect(screen.getByText("Trabalhando nisso…")).toBeInTheDocument();
  });

  it("reopening replays a reply that was working and ends it", async () => {
    thread("c-1", [person("m-1", "Oi"), message("r-1", { status: "working" })], [{ id: "m-1", role: "user", parts: [] }]);
    respond("GET", "/v1/messages/r-1/stream", ended({ type: "start", messageId: "r-1" }, ...text("t-1", "Pronto, guardei.")));
    renderChat();

    expect(await screen.findByText("Pronto, guardei.")).toBeInTheDocument();
    expect(screen.queryByText("Trabalhando nisso…")).not.toBeInTheDocument();
    expect(screen.getAllByRole("article", { name: "Resposta do Acervo" })).toHaveLength(1);
  });

  it("a dropped stream is read again from its start and the reply shows once", async () => {
    thread("c-1", [person("m-1", "Oi"), message("r-1", { status: "working" })]);
    const start = [{ type: "start", messageId: "r-1" }, { type: "text-start", id: "t-1" }, { type: "text-delta", id: "t-1", delta: "Pronto, " }];
    let reads = 0;
    respond("GET", "/v1/messages/r-1/stream", () => {
      reads += 1;
      if (reads > 1) return ended(...start, { type: "text-delta", id: "t-1", delta: "guardei." }, { type: "text-end", id: "t-1" })();
      const body = new ReadableStream({
        start: (stream) => {
          stream.enqueue(new TextEncoder().encode(lines(start)));
          setTimeout(() => stream.error(new TypeError("network error")), 50);
        },
      });
      return { body };
    });
    renderChat();

    expect(await screen.findByText("Pronto,")).toBeInTheDocument();
    expect(await screen.findByText("Pronto, guardei.", {}, { timeout: 4000 })).toBeInTheDocument();
    const [reply] = screen.getAllByRole("article", { name: "Resposta do Acervo" });
    expect(reply?.textContent?.match(/Pronto/g)).toHaveLength(1);
    expect(reads).toBe(2);
  }, 10_000);

  it("a proposal replayed as it was never takes back a newer state", async () => {
    thread("c-1", [person("m-1", "Vistoria por vídeo até 300 m²."), message("r-1", { status: "working" })]);
    const applied = proposal(append, { status: "applied", accepted_by: "person", updated_at: "2026-10-22T10:01:00Z" });
    respond(
      "GET",
      "/v1/messages/r-1/stream",
      ended(
        { type: "start", messageId: "r-1" },
        { type: "data-proposal", id: "p-1", data: applied },
        { type: "data-proposal", id: "p-1", data: proposal(append) },
      ),
    );
    renderChat();

    const card = await screen.findByRole("region", { name: "Acréscimo" });
    await waitFor(() => expect(screen.queryByText("Trabalhando nisso…")).not.toBeInTheDocument());
    expect(within(card).getByText("Aplicada")).toBeInTheDocument();
    expect(within(card).queryByRole("button", { name: "Aceitar" })).not.toBeInTheDocument();
  });

  it("a reply that was retried is not shown, so it cannot be retried again", async () => {
    thread("c-1", [
      person("m-1", "Guarda isso."),
      message("r-1", { status: "failed", error: "model down" }),
      message("r-2", { text: "Agora foi.", replaces_id: "r-1" }),
    ]);
    renderChat();

    expect(await screen.findByText("Agora foi.")).toBeInTheDocument();
    expect(screen.getAllByRole("article", { name: "Resposta do Acervo" })).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Tentar de novo" })).not.toBeInTheDocument();
  });

  it("a proposal of a deleted conversation opens its card in the list", async () => {
    const orphan = proposal(append, { conversation_id: "c-9", message_id: "r-9" });
    respond("GET", "/v1/kbs/kb-1/proposals", (url) => ({
      body: url.searchParams.get("status") === "pending" ? [{ ...orphan, agent_name: "Chat do Acervo", conversation_title: null }] : [],
    }));
    renderChat();

    await userEvent.click(await screen.findByRole("button", { name: "Ver todas" }));
    const list = screen.getByRole("list", { name: "Propostas esperando" });
    await userEvent.click(within(list).getByRole("button", { name: /Acréscimo/ }));
    expect(within(list).getByRole("region", { name: "Acréscimo" })).toBeInTheDocument();
    expect(calls.some((call) => call.path.startsWith("/v1/conversations/c-9"))).toBe(false);
  });

  it("a proposal part shows its card, and a later part with its id updates it", async () => {
    thread("c-1", [person("m-1", "Vistoria por vídeo até 300 m²."), message("r-1", { status: "working" })]);
    respond(
      "GET",
      "/v1/messages/r-1/stream",
      ended(
        { type: "start", messageId: "r-1" },
        { type: "data-proposal", id: "p-1", data: proposal(append) },
        {
          type: "data-proposal",
          id: "p-1",
          data: proposal(append, { status: "applied", accepted_by: "auto", updated_at: "2026-10-22T10:01:00Z" }),
        },
      ),
    );
    renderChat();

    const card = await screen.findByRole("region", { name: "Acréscimo" });
    expect(card).toHaveTextContent("Porto Seguro / Residencial / Vistoria.md § Como agendar");
    expect(await within(card).findByText("Aplicada automaticamente")).toBeInTheDocument();
    expect(screen.getAllByRole("region", { name: "Acréscimo" })).toHaveLength(1);
  });

  it("citations open the page at its section and the PDF at its page", async () => {
    thread(
      "c-1",
      [person("m-1", "Qual o prazo?"), message("r-1", { grounded: true })],
      [
        {
          id: "r-1",
          role: "assistant",
          parts: [
            { type: "text", text: "Até 60 dias após o vencimento [1]. Depois vira apólice nova [2]." },
            ...[
              { marker: 1, kind: "page", node_id: "page-1", path: "Bradesco/Residencial/Renovação e prazos", anchor: "prazos", page: null },
              { marker: 2, kind: "file", node_id: "file-1", path: "Bradesco/Residencial/Condições Gerais 2026.pdf", anchor: null, page: 88 },
            ].map((citation) => ({
              type: "source-document",
              sourceId: `[${citation.marker}]`,
              mediaType: citation.kind === "file" ? "application/pdf" : "text/markdown",
              title: citation.path,
              providerMetadata: { acervo: citation },
            })),
          ],
        },
      ],
    );
    renderChat();

    const reply = await screen.findByRole("article", { name: "Resposta do Acervo" });
    expect(within(reply).getByRole("link", { name: "1" })).toHaveAttribute("href", "/kbs/kb-1/n/page-1#prazos");
    const sources = within(reply).getByRole("list", { name: "Fontes" });
    expect(within(sources).getByRole("link", { name: /Renovação e prazos/ })).toHaveAttribute("href", "/kbs/kb-1/n/page-1#prazos");
    const pdf = within(sources).getByRole("link", { name: /Condições Gerais 2026/ });
    expect(pdf).toHaveAttribute("href", "/kbs/kb-1/n/file-1?p=88");
    expect(pdf).toHaveTextContent("p. 88");
    expect(screen.queryByText("Isso não veio da base.")).not.toBeInTheDocument();
  });

  it("a general answer says it did not come from the base, with no way to change how it was understood", async () => {
    thread("c-1", [person("m-1", "Oi!"), message("r-1", { text: "Oi! Em que posso ajudar?", grounded: false })]);
    renderChat();

    expect(await screen.findByText("Oi! Em que posso ajudar?")).toBeInTheDocument();
    expect(screen.getByText("Isso não veio da base.")).toBeInTheDocument();
    expect(screen.queryByText(/mudar/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Entendi como/)).not.toBeInTheDocument();
  });

  it("a failed reply retries and follows the new reply's stream", async () => {
    thread("c-1", [person("m-1", "Guarda isso."), message("r-1", { status: "failed", error: "model down" })]);
    let answer: (reply: { status: number; body: unknown }) => void = () => {};
    respond("POST", "/v1/messages/r-1/retry", () => new Promise((resolve) => (answer = resolve)));
    respond("GET", "/v1/messages/r-2/stream", ended({ type: "start", messageId: "r-2" }, ...text("t-1", "Agora foi.")));
    renderChat();

    expect(await screen.findByText("Não consegui terminar esta mensagem. Nada foi aplicado.")).toBeInTheDocument();
    expect(screen.queryByText("model down")).not.toBeInTheDocument();
    const retry = screen.getByRole("button", { name: "Tentar de novo" });
    await userEvent.click(retry);
    expect(retry).toBeDisabled();

    answer({ status: 201, body: message("r-2", { status: "working", replaces_id: "r-1" }) });
    expect(await screen.findByText("Agora foi.")).toBeInTheDocument();
    expect(screen.queryByText("Não consegui terminar esta mensagem. Nada foi aplicado.")).not.toBeInTheDocument();
  });

  it("the pending list counts every proposal, names its agent and opens its conversation", async () => {
    const waiting = proposal(append, { conversation_id: "c-2", message_id: "r-9" });
    respond("GET", "/v1/kbs/kb-1/proposals", (url) => ({
      body: url.searchParams.get("status") === "pending" ? [{ ...waiting, agent_name: "Claude", conversation_title: "Vistorias" }] : [],
    }));
    thread(
      "c-2",
      [message("r-9", { conversation_id: "c-2", text: "Proponho." })],
      [{ id: "r-9", role: "assistant", parts: [{ type: "text", text: "Proponho." }, { type: "data-proposal", id: "p-1", data: waiting }] }],
    );
    renderChat();

    expect(await screen.findByText("1 proposta esperando você")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Ver todas" }));
    const list = screen.getByRole("list", { name: "Propostas esperando" });
    expect(list).toHaveTextContent("Claude · Vistorias");

    await userEvent.click(within(list).getByRole("button", { name: /Acréscimo/ }));
    expect(await screen.findByText("Proponho.")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Acréscimo" })).toBeInTheDocument();
  });

  it("the list shows what agents applied automatically, each with Desfazer", async () => {
    const auto = proposal(append, { id: "p-9", status: "applied", accepted_by: "auto", conversation_id: null, message_id: null });
    respond("GET", "/v1/kbs/kb-1/proposals", (url) => ({
      body: url.searchParams.get("status") === "applied" ? [{ ...auto, agent_name: "Claude", conversation_title: null }] : [],
    }));
    respond("POST", "/v1/proposals/p-9/undo", { status: 201, body: proposal(undo, { id: "p-10", status: "applied", accepted_by: "auto" }) });
    renderChat();

    expect(await screen.findByText("1 mudança aplicada automaticamente")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Ver todas" }));
    const applied = screen.getByRole("region", { name: "Aplicadas automaticamente" });
    expect(applied).toHaveTextContent("Porto Seguro / Residencial / Vistoria.md § Como agendar");
    expect(applied).toHaveTextContent("Claude");

    await userEvent.click(within(applied).getByRole("button", { name: "Desfazer" }));
    expect(await within(applied).findByText("Desfeita")).toBeInTheDocument();
    expect(calls.filter((call) => call.method === "POST" && call.path === "/v1/proposals/p-9/undo")).toHaveLength(1);
  });

  it("deleting a conversation confirms, calls DELETE and leaves the list; the chat starts anew", async () => {
    thread("c-1", [person("m-1", "Antes de apagar.")]);
    respond("DELETE", "/v1/conversations/c-1", () => {
      conversations = conversations.filter((c) => c.id !== "c-1");
      return { body: conversation("c-1", "Prazos") };
    });
    renderChat();
    expect(await screen.findByText("Antes de apagar.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Conversas anteriores" }));
    await userEvent.click(await screen.findByRole("button", { name: "Apagar Prazos" }));
    const dialog = screen.getByRole("dialog", { name: "Apagar “Prazos”?" });
    expect(calls.filter((call) => call.method === "DELETE")).toHaveLength(0);

    await userEvent.click(within(dialog).getByRole("button", { name: "Apagar conversa" }));
    await waitFor(() => expect(calls.filter((call) => call.method === "DELETE" && call.path === "/v1/conversations/c-1")).toHaveLength(1));
    const list = screen.getByRole("list", { name: "Conversas anteriores" });
    await waitFor(() => expect(list).not.toHaveTextContent("Prazos"));
    expect(list).toHaveTextContent("Vistorias");

    await userEvent.click(screen.getByRole("button", { name: "Voltar à conversa" }));
    expect(screen.queryByText("Antes de apagar.")).not.toBeInTheDocument();
    expect(screen.getByText("Conte o que aprendeu")).toBeInTheDocument();
  });

  it("a refetch that reorders the list keeps the open conversation and what is typed", async () => {
    thread("c-1", [person("m-1", "Primeira.")]);
    thread("c-2", [person("m-9", "Outra.", "c-2")]);
    const { queryClient } = renderChat();
    expect(await screen.findByText("Primeira.")).toBeInTheDocument();
    await userEvent.type(box(), "rascunho");

    conversations = [conversation("c-2", "Vistorias"), conversation("c-1", "Prazos")];
    await act(() => queryClient.refetchQueries({ queryKey: ["conversations"] }));
    // Long enough for a switched conversation to load its thread.
    await act(() => new Promise((resolve) => setTimeout(resolve, 50)));

    expect(screen.getByText("Primeira.")).toBeInTheDocument();
    expect(screen.queryByText("Outra.")).not.toBeInTheDocument();
    expect(box()).toHaveValue("rascunho");
  });

  it("past conversations reopen", async () => {
    thread("c-2", [person("m-9", "Antiga.", "c-2")]);
    renderChat();

    await userEvent.click(screen.getByRole("button", { name: "Conversas anteriores" }));
    await userEvent.click(await screen.findByRole("button", { name: /^Vistorias/ }));
    expect(await screen.findByText("Antiga.")).toBeInTheDocument();
  });
});
