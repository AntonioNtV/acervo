import "@testing-library/jest-dom/vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { calls, renderWithApi, resetApi, respond } from "../../api/testing";
import type { Agent } from "../../data/agents";
import { AgentsScreen } from "./AgentsScreen";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

function agent(id: string, name: string, extra: Partial<Agent> = {}): Agent {
  return {
    id,
    kb_id: "kb-1",
    name,
    mode: "ask",
    built_in: false,
    token_hint: "3f9a",
    last_used_at: null,
    revoked_at: null,
    created_at: "2026-10-20T10:00:00Z",
    ...extra,
  };
}

let agents: Agent[];

beforeEach(() => {
  localStorage.clear();
  resetApi();
  agents = [
    agent("chat", "Chat do Acervo", { built_in: true, token_hint: null }),
    agent("support", "Suporte ao corretor", { mode: "auto", last_used_at: new Date().toISOString() }),
  ];
  respond("GET", "/v1/kbs/kb-1/agents", () => ({ body: agents }));
  respond("GET", "/v1/kbs", { body: [] });
});

function renderScreen() {
  return renderWithApi(
    <MemoryRouter initialEntries={["/kbs/kb-1/agents"]}>
      <Routes>
        <Route path="/kbs/:kbId/agents" element={<AgentsScreen />} />
      </Routes>
    </MemoryRouter>,
  );
}

const row = async (name: string) => (await screen.findByText(name)).closest("li")!;

describe("AgentsScreen", () => {
  it("lists the base's agents with kind, mode and token hint", async () => {
    renderScreen();

    const chat = await row("Chat do Acervo");
    expect(chat).toHaveTextContent("embutido");
    expect(within(chat).getByRole("button", { name: "Perguntar" })).toHaveAttribute("aria-pressed", "true");
    const support = await row("Suporte ao corretor");
    expect(support).toHaveTextContent("MCP · token acv_…3f9a · usado agora");
    expect(within(support).getByRole("button", { name: "Automático" })).toHaveAttribute("aria-pressed", "true");
  });

  it("switching the mode PATCHes the agent", async () => {
    respond("PATCH", "/v1/agents/chat", (_url, body) => {
      agents[0] = { ...agents[0]!, ...(body as Partial<Agent>) };
      return { body: agents[0] };
    });
    renderScreen();

    const chat = await row("Chat do Acervo");
    await userEvent.click(within(chat).getByRole("button", { name: "Automático" }));

    expect(calls.find((c) => c.method === "PATCH")).toMatchObject({ path: "/v1/agents/chat", body: { mode: "auto" } });
    await waitFor(() =>
      expect(within(chat).getByRole("button", { name: "Automático" })).toHaveAttribute("aria-pressed", "true"),
    );
  });

  it("connecting shows the address and the token once", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    // jsdom has no clipboard.
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    respond("POST", "/v1/kbs/kb-1/agents", (_url, body) => {
      const created = agent("sales", (body as { name: string }).name, { token_hint: "71c2" });
      agents.push(created);
      return { status: 201, body: { ...created, token: "acv_secret71c2" } };
    });
    renderScreen();
    await row("Chat do Acervo");

    await userEvent.click(screen.getByRole("button", { name: "Conectar agente" }));
    const dialog = screen.getByRole("dialog", { name: "Conectar agente" });
    await userEvent.type(within(dialog).getByLabelText("Nome"), "Bot de vendas");
    await userEvent.click(within(dialog).getByRole("button", { name: "Conectar" }));

    const connection = await within(dialog).findByLabelText("Conexão");
    expect(connection).toHaveTextContent(`${window.location.origin}/mcp`);
    expect(connection).toHaveTextContent("Bearer acv_secret71c2");
    await userEvent.click(within(dialog).getByRole("button", { name: "Copiar" }));
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Bearer acv_secret71c2"));

    await userEvent.click(within(dialog).getByRole("button", { name: "Concluir" }));
    expect(await row("Bot de vendas")).toHaveTextContent("acv_…71c2");
    expect(screen.queryByText(/acv_secret71c2/)).not.toBeInTheDocument();
  });

  it("revoking asks first, then DELETEs", async () => {
    respond("DELETE", "/v1/agents/support", () => {
      agents[1] = { ...agents[1]!, revoked_at: new Date().toISOString() };
      return { body: agents[1] };
    });
    renderScreen();

    const support = await row("Suporte ao corretor");
    await userEvent.click(within(support).getByRole("button", { name: "Revogar" }));
    const dialog = screen.getByRole("dialog", { name: "Revogar Suporte ao corretor?" });
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    await userEvent.click(within(dialog).getByRole("button", { name: "Revogar" }));

    expect(calls.find((c) => c.method === "DELETE")?.path).toBe("/v1/agents/support");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(await row("Suporte ao corretor")).toHaveTextContent("revogado agora");
    expect(within(support).queryByRole("button", { name: "Revogar" })).not.toBeInTheDocument();
  });

  it("the built-in chat cannot be revoked", async () => {
    renderScreen();

    const chat = await row("Chat do Acervo");
    expect(within(chat).queryByRole("button", { name: "Revogar" })).not.toBeInTheDocument();
  });
});
