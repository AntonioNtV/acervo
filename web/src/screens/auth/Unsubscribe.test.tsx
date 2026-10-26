import "@testing-library/jest-dom/vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, resetApi, respond } from "../../api/testing";
import { renderAuth } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

// What the server seals: base64url JSON, a dot, the signature.
const token = `${btoa(JSON.stringify({ account: "acc-1", notification: "invites", purpose: "unsubscribe" })).replace(/=+$/, "")}.sig`;

beforeEach(() => {
  localStorage.clear();
  resetApi();
});

describe("Unsubscribe", () => {
  it("turns the toggle off on opening, signed out, and says which emails stop", async () => {
    respond("POST", `/v1/auth/unsubscribe/${token}`, { status: 204, body: undefined });
    renderAuth(`/descadastro/${token}`);

    expect(await screen.findByRole("heading", { name: "Você não recebe mais estes emails" })).toBeInTheDocument();
    expect(
      screen.getByText("Desligamos “Convites e acessos”. Os alertas de segurança e os códigos continuam."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Notificações" })).toHaveAttribute("href", "/conta/notificacoes");
    expect(calls.filter((call) => call.method === "POST")).toHaveLength(1);
  });

  it("Voltar a receber turns it back on", async () => {
    respond("POST", `/v1/auth/unsubscribe/${token}`, { status: 204, body: undefined });
    respond("POST", `/v1/auth/resubscribe/${token}`, { status: 204, body: undefined });
    renderAuth(`/descadastro/${token}`);

    await userEvent.click(await screen.findByRole("button", { name: "Voltar a receber" }));

    expect(await screen.findByRole("heading", { name: "Você volta a receber" })).toBeInTheDocument();
    expect(screen.getByText("“Convites e acessos” está ligado de novo.")).toBeInTheDocument();
    expect(calls.at(-1)?.path).toBe(`/v1/auth/resubscribe/${token}`);
  });

  it("a changed link says it is not valid", async () => {
    respond("POST", "/v1/auth/unsubscribe/forged", { status: 404, body: { error: "not_found", message: "no" } });
    renderAuth("/descadastro/forged");

    expect(await screen.findByRole("heading", { name: "Este link não vale" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Entrar" })).toHaveAttribute("href", "/entrar");
  });
});
