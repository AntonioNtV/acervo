import "@testing-library/jest-dom/vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, resetApi, respond } from "../../api/testing";
import type { InvitePreview } from "../../data/orgSettings";
import { signedIn } from "../settings/testing";
import { renderAuth } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

const invite: InvitePreview = {
  organization: "Seguros SA",
  organization_id: "org-1",
  base: null,
  kb_id: null,
  inviter: "Marina Costa",
  role: "member",
  email: "julia@corretora.com",
  expired: false,
};

beforeEach(() => {
  localStorage.clear();
  resetApi();
  respond("GET", "/v1/invites/by-token/tok-1", { body: invite });
});

describe("Invite", () => {
  it("signed in with the invited email, accepts and lands on the organization", async () => {
    signedIn({ email: "Julia@corretora.com", name: "Julia Reis" });
    respond("POST", "/v1/invites/accept", { body: invite });
    const router = renderAuth("/convite/tok-1");

    expect(await screen.findByRole("heading", { name: "Marina Costa convidou você" })).toBeInTheDocument();
    expect(screen.getByText("como Membro")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Aceitar convite" }));

    expect(await screen.findByText("Dentro")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/bases");
    expect(calls.find((call) => call.path === "/v1/invites/accept")?.body).toEqual({ token: "tok-1" });
    expect(localStorage.getItem("acervo.org")).toBe("org-1");
  });

  it("a used link, signed in as who joined with it, lands on the organization instead of Convite indisponível", async () => {
    signedIn({ email: "julia@corretora.com", name: "Julia Reis" });
    respond("GET", "/v1/invites/by-token/tok-1", { status: 400, body: { error: "code_invalid", message: "used" } });
    respond("POST", "/v1/invites/accept", { body: invite });
    const router = renderAuth("/convite/tok-1");

    expect(await screen.findByText("Dentro")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/bases");
    expect(localStorage.getItem("acervo.org")).toBe("org-1");
  });

  it("signed in with another email, says who the invite is for and offers to switch account", async () => {
    signedIn({ email: "antonio@segura.com.br" });
    renderAuth("/convite/tok-1");

    expect(
      await screen.findByRole("heading", { name: "Este convite é para julia@corretora.com" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Entrar com outra conta" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Aceitar convite" })).not.toBeInTheDocument();
    expect(calls.some((call) => call.path === "/v1/invites/accept")).toBe(false);
  });

  it("without an account, Continuar com email opens Criar conta with the invited email", async () => {
    respond("GET", "/v1/auth/me", { status: 401, body: { error: "unauthorized", message: "no" } });
    const router = renderAuth("/convite/tok-1");

    expect(await screen.findByText(/O convite é para julia@corretora.com/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Continuar com email" }));

    expect(await screen.findByRole("heading", { name: "Criar conta" })).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveValue("julia@corretora.com");
    // Confirming the email comes back to the link, which then lands where it leads.
    expect(router.state.location.search).toBe(`?next=${encodeURIComponent("/convite/tok-1")}`);
  });
});
