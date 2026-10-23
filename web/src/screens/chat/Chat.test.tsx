import "@testing-library/jest-dom/vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, node, renderWithApi, resetApi, respond } from "../../api/testing";
import { Chat } from "./Chat";
import { append, message, proposal, T0 } from "./testing";

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
const sse = (...events: unknown[]) => events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join("");
const never = () => new Promise<never>(() => {});

beforeEach(() => {
  resetApi();
  editor.selection = "";
  FakeXhr.sent = [];
  vi.stubGlobal("XMLHttpRequest", FakeXhr);
  respond("GET", "/v1/kbs", { body: [{ id: "kb-1", name: "Seguros · Operação" }] });
  respond("GET", "/v1/kbs/kb-1/conversations", { body: [conversation("c-1", "Prazos"), conversation("c-2", "Vistorias")] });
  respond("GET", "/v1/conversations/c-1/messages", { body: [] });
  respond("GET", "/v1/conversations/c-1/events", never);
  respond("GET", "/v1/kbs/kb-1/proposals", { body: [] });
  respond("GET", "/v1/nodes/page-1", {
    body: { ...node("page-1", "page", "Renovação e prazos"), path: "Bradesco/Renovação e prazos", page: null, file: null, versions: 0 },
  });
});

afterEach(() => vi.unstubAllGlobals());

function renderChat() {
  return renderWithApi(<Chat kbId="kb-1" nodeId="page-1" onClose={() => {}} />);
}

const box = () => screen.getByRole("textbox", { name: "Mensagem" });

describe("Chat", () => {
  it("has one box and no mode tabs", async () => {
    renderChat();
    expect(await screen.findByText("em Seguros · Operação")).toBeInTheDocument();
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
    expect(screen.queryByText("Capturar")).not.toBeInTheDocument();
    expect(screen.queryByText("Perguntar")).not.toBeInTheDocument();
  });

  it("sending posts the text with the open page and the selection, and Enter sends", async () => {
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

    sent.reply(201, {
      message: message("m-1", { role: "person", text: "Isso também vale para o Auto.\nGuarda lá." }),
      reply: message("r-1", { status: "working" }),
    });
    expect(await screen.findByText("Trabalhando nisso…")).toBeInTheDocument();
    expect(box()).toHaveValue("");
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
    await userEvent.upload(screen.getByLabelText("Arquivos para anexar"), file);
    expect(screen.getByRole("button", { name: "Tirar CG_Residencial_2026.pdf" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    await waitFor(() => expect(FakeXhr.sent).toHaveLength(1));
    expect(FakeXhr.sent[0]?.form?.getAll("files")).toEqual([file]);
  });

  it("a new conversation starts with the first message", async () => {
    respond("POST", "/v1/kbs/kb-1/conversations", { status: 201, body: conversation("c-3", "") });
    respond("GET", "/v1/conversations/c-3/messages", { body: [] });
    respond("GET", "/v1/conversations/c-3/events", never);
    renderChat();
    await userEvent.click(screen.getByRole("button", { name: "Nova conversa" }));
    await userEvent.type(box(), "Um fato.{Enter}");

    await waitFor(() => expect(FakeXhr.sent[0]?.path).toBe("/v1/conversations/c-3/messages"));
  });

  it("a step event shows live in the reply", async () => {
    respond("GET", "/v1/conversations/c-1/messages", { body: [message("r-1", { status: "working" })] });
    respond("GET", "/v1/conversations/c-1/events", {
      body: sse({ type: "step", message_id: "r-1", step: "file_attachment", detail: "CG_Residencial_2026.pdf" }),
    });
    renderChat();

    const steps = await screen.findByRole("list", { name: "Passos" });
    expect(steps).toHaveTextContent("procurando onde salvar");
    expect(steps).toHaveTextContent("CG_Residencial_2026.pdf");
  });

  it("a proposal event shows its card in the reply", async () => {
    respond("GET", "/v1/conversations/c-1/messages", { body: [message("r-1", { text: "Acréscimo: Vistoria" })] });
    respond("GET", "/v1/conversations/c-1/events", { body: sse({ type: "proposal", proposal: proposal(append) }) });
    renderChat();

    const card = await screen.findByRole("region", { name: "Acréscimo" });
    expect(card).toHaveTextContent("Porto Seguro / Residencial / Vistoria.md § Como agendar");
  });

  it("a failed reply offers to try again", async () => {
    respond("GET", "/v1/conversations/c-1/messages", {
      body: [message("r-1", { status: "failed", error: "model down" })],
    });
    respond("POST", "/v1/messages/r-1/retry", { status: 201, body: message("r-2", { status: "working", replaces_id: "r-1" }) });
    renderChat();

    expect(await screen.findByText("Não consegui terminar esta mensagem. Nada foi aplicado.")).toBeInTheDocument();
    expect(screen.queryByText("model down")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
    await waitFor(() =>
      expect(calls.find((call) => call.path === "/v1/messages/r-1/retry")).toBeDefined(),
    );
  });

  it("the pending list counts every proposal, names its agent and opens its conversation", async () => {
    respond("GET", "/v1/kbs/kb-1/proposals", {
      body: [
        { ...proposal(append, { conversation_id: "c-2", message_id: "r-9" }), agent_name: "Claude", conversation_title: "Vistorias" },
      ],
    });
    respond("GET", "/v1/conversations/c-2/messages", { body: [message("r-9", { conversation_id: "c-2", text: "Proponho." })] });
    respond("GET", "/v1/conversations/c-2/events", never);
    renderChat();

    expect(await screen.findByText("1 proposta esperando você")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Ver todas" }));
    const list = screen.getByRole("list", { name: "Propostas esperando" });
    expect(list).toHaveTextContent("Claude · Vistorias");

    await userEvent.click(within(list).getByRole("button", { name: /Acréscimo/ }));
    expect(await screen.findByText("Proponho.")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Acréscimo" })).toBeInTheDocument();
  });

  it("past conversations reopen", async () => {
    respond("GET", "/v1/conversations/c-2/messages", { body: [message("m-9", { conversation_id: "c-2", role: "person", text: "Antiga." })] });
    respond("GET", "/v1/conversations/c-2/events", never);
    renderChat();

    await userEvent.click(screen.getByRole("button", { name: "Conversas anteriores" }));
    await userEvent.click(await screen.findByRole("button", { name: /Vistorias/ }));
    expect(await screen.findByText("Antiga.")).toBeInTheDocument();
  });
});
