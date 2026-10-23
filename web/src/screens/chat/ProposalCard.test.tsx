import "@testing-library/jest-dom/vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, renderWithApi, resetApi, respond } from "../../api/testing";
import type { Payload } from "../../data/proposals";
import { FileGroup, ProposalCard } from "./ProposalCard";
import { append, conflict, createPage, message, move, proposal, rename, replacePdf, savePdf, staged, undo } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

beforeEach(() => {
  resetApi();
  for (const action of ["accept", "reject", "other-place", "undo"])
    respond("POST", `/v1/proposals/p-1/${action}`, (_url, body) => ({
      body: proposal(append, { status: action === "reject" ? "rejected" : "applied", reject_reason: (body as { reason?: never })?.reason ?? null }),
    }));
  respond("PATCH", "/v1/proposals/p-1", (_url, body) => ({ body: proposal(append, { edited_payload: body as Payload }) }));
});

const posted = (path: string) => calls.filter((call) => call.method !== "GET" && call.path === path);

describe("ProposalCard", () => {
  it.each([
    ["Acréscimo", append, "Porto Seguro / Residencial / Vistoria.md § Como agendar", ["Aceitar", "Editar", "Rejeitar"]],
    ["Página nova", createPage, "Bradesco / Residencial / Checklist de vistoria.md", ["Aceitar", "Editar", "Rejeitar"]],
    ["Salvar PDF", savePdf, "Bradesco / Residencial / Condições Gerais 2026.pdf", ["Aceitar", "Editar", "Rejeitar"]],
    ["Nova versão", replacePdf, "Bradesco / Auto / Tabela auto 2025.pdf", ["Aceitar", "Rejeitar"]],
    ["Mover", move, "Bradesco / Auto / Tabela auto 2025.pdf → Bradesco / Auto / Arquivo", ["Aceitar", "Rejeitar"]],
    ["Renomear", rename, "Bradesco / Auto / Renov → Renovação", ["Aceitar", "Editar", "Rejeitar"]],
    ["Desfazer", undo, "Porto Seguro / Residencial / Vistoria", ["Desfazer", "Rejeitar"]],
  ])("%s shows where it goes before its buttons, and accepting calls the API", async (kind, payload, where, buttons) => {
    renderWithApi(<ProposalCard proposal={proposal(payload, { staged })} />);

    const card = screen.getByRole("region", { name: kind });
    expect(card).toHaveTextContent(where);
    expect(within(card).getAllByRole("button").map((button) => button.textContent)).toEqual(buttons);

    await userEvent.click(within(card).getByRole("button", { name: buttons[0] }));
    await waitFor(() => expect(posted("/v1/proposals/p-1/accept")).toHaveLength(1));
    expect(await within(card).findByText("Aplicada")).toBeInTheDocument();
  });

  it("an addition shows its lines as a diff under the section", () => {
    renderWithApi(<ProposalCard proposal={proposal(append)} />);
    expect(screen.getByText("## Como agendar")).toBeInTheDocument();
    expect(screen.getByText(/\+ - Por vídeo/)).toBeInTheDocument();
  });

  it("rejecting asks a reason first and sends it", async () => {
    renderWithApi(<ProposalCard proposal={proposal(append)} />);

    await userEvent.click(screen.getByRole("button", { name: "Rejeitar" }));
    expect(posted("/v1/proposals/p-1/reject")).toHaveLength(0);
    expect(screen.getByText("Por quê?")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Lugar errado" }));
    await waitFor(() => expect(posted("/v1/proposals/p-1/reject")).toMatchObject([{ body: { reason: "wrong_place" } }]));
    expect(await screen.findByText("Rejeitada · Lugar errado")).toBeInTheDocument();
  });

  it("a conflict with no specific line says the new text goes at the end of the section", () => {
    renderWithApi(<ProposalCard proposal={proposal({ ...conflict, current: "" } as typeof conflict)} />);
    expect(screen.getByRole("region", { name: "Conflito" })).toHaveTextContent(
      "Na página hojeNenhuma linha específica; o texto novo entra no fim da seção.",
    );
  });

  it("a conflict shows both texts and its three choices", async () => {
    renderWithApi(<ProposalCard proposal={proposal(conflict)} />);
    const card = screen.getByRole("region", { name: "Conflito" });
    expect(card).toHaveTextContent("Na página hojeAté 60 dias após o vencimento.");
    expect(card).toHaveTextContent("Você disse agoraAté 45 dias, a partir de novembro.");

    await userEvent.click(screen.getByRole("button", { name: "Guardar as duas com nota" }));
    await waitFor(() => expect(posted("/v1/proposals/p-1/accept")).toHaveLength(1));
    const [edit] = posted("/v1/proposals/p-1");
    expect((edit?.body as { new: string }).new).toMatch(/^Até 60 dias após o vencimento.\nAté 45 dias, a partir de novembro.\n_Nota/);
  });

  it.each([
    ["Usar a nova", "accept", undefined],
    ["Manter a atual", "reject", { reason: "wrong_info" }],
  ])("a conflict's %s calls %s", async (button, action, body) => {
    renderWithApi(<ProposalCard proposal={proposal(conflict)} />);
    await userEvent.click(screen.getByRole("button", { name: button }));
    await waitFor(() => expect(posted(`/v1/proposals/p-1/${action}`)).toMatchObject([{ body }]));
  });

  it("editing sends the person's version", async () => {
    renderWithApi(<ProposalCard proposal={proposal(append)} />);
    await userEvent.click(screen.getByRole("button", { name: "Editar" }));
    const lines = screen.getByRole("textbox", { name: "Linhas a acrescentar" });
    await userEvent.clear(lines);
    await userEvent.type(lines, "- Por vídeo, até 300 m².");
    await userEvent.click(screen.getByRole("button", { name: "Salvar edição" }));

    await waitFor(() =>
      expect(posted("/v1/proposals/p-1")).toMatchObject([{ method: "PATCH", body: { ...append, lines: ["- Por vídeo, até 300 m²."] } }]),
    );
  });

  it("a second close place offers Outro lugar", async () => {
    const alternatives = [{ node_id: "porto", path: "Porto Seguro", landing: "new_page" as const, probability: 0.31 }];
    renderWithApi(<ProposalCard proposal={proposal(createPage, { alternatives })} />);
    await userEvent.click(screen.getByRole("button", { name: "Outro lugar" }));
    await waitFor(() => expect(posted("/v1/proposals/p-1/other-place")).toHaveLength(1));
  });

  it("not sure where: three places to choose, another folder, or leave it waiting", async () => {
    const alternatives = [
      { node_id: "residencial", path: "Bradesco/Residencial", landing: "new_page" as const, probability: 0.48 },
      { node_id: "processos", path: "Processos internos", landing: "new_page" as const, probability: 0.31 },
      { node_id: null, path: "", landing: "new_page" as const, probability: 0.14 },
    ];
    renderWithApi(<ProposalCard proposal={proposal(createPage, { alternatives })} />);

    expect(screen.getByText("Fiquei entre estes lugares. Onde isso deve morar?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Escolher outra pasta…" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Aceitar" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Processos internos \/ Checklist de vistoria.md/ }));
    await waitFor(() =>
      expect(posted("/v1/proposals/p-1")).toMatchObject([
        { body: { ...createPage, parent_id: "processos", parent_path: "Processos internos" } },
      ]),
    );
    expect(posted("/v1/proposals/p-1/accept")).toHaveLength(0);
  });

  it("an applied proposal can be undone", async () => {
    respond("POST", "/v1/proposals/p-1/undo", { status: 201, body: proposal(undo, { id: "p-2", message_id: null }) });
    renderWithApi(<ProposalCard proposal={proposal(append, { status: "applied", accepted_by: "auto" })} />);

    expect(screen.getByText("Aplicada automaticamente")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Desfazer" }));
    await waitFor(() => expect(posted("/v1/proposals/p-1/undo")).toHaveLength(1));
    expect(await screen.findByRole("region", { name: "Desfazer" })).toBeInTheDocument();
  });

  it("a stale proposal offers Refazer and calls redo", async () => {
    respond("POST", "/v1/proposals/p-1/redo", { status: 201, body: message("r-2", { status: "working" }) });
    renderWithApi(<ProposalCard proposal={proposal(append, { status: "stale" })} />);

    expect(screen.getByText("A página mudou.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Aceitar" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Refazer" }));
    await waitFor(() => expect(posted("/v1/proposals/p-1/redo")).toHaveLength(1));
  });

  it("several files accept all at once", async () => {
    const files = [proposal(savePdf, { staged }), proposal(replacePdf, { id: "p-1b", staged })];
    respond("POST", "/v1/proposals/p-1b/accept", { body: proposal(replacePdf, { id: "p-1b", status: "applied" }) });
    renderWithApi(<FileGroup proposals={files} onReview={() => {}} />);

    expect(screen.getByText("Salvar Condições Gerais 2026.pdf")).toBeInTheDocument();
    expect(screen.getByText("Nova versão de Tabela auto 2025.pdf")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Aceitar todos os 2" }));
    await waitFor(() => expect(posted("/v1/proposals/p-1b/accept")).toHaveLength(1));
    expect(posted("/v1/proposals/p-1/accept")).toHaveLength(1);
  });
});
