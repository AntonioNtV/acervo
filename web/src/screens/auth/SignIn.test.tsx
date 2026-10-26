import "@testing-library/jest-dom/vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, resetApi, respond } from "../../api/testing";
import { renderAuth } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

const SIGN_IN = "/v1/auth/sign-in";

beforeEach(() => {
  localStorage.clear();
  resetApi();
});

async function signIn(email: string, password: string) {
  await userEvent.type(screen.getByLabelText("Email"), email);
  await userEvent.type(screen.getByLabelText("Senha"), password);
  await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
}

describe("SignIn", () => {
  it("a wrong email or password gets one message that does not say which", async () => {
    respond("POST", SIGN_IN, { status: 401, body: { error: "invalid_credentials", message: "no" } });
    const router = renderAuth("/entrar");

    await signIn("antonio@segura.com.br", "errada-mesmo");

    expect(await screen.findByRole("alert")).toHaveTextContent("Email ou senha incorretos.");
    expect(screen.getByLabelText("Senha")).toHaveAttribute("aria-invalid", "true");
    expect(router.state.location.pathname).toBe("/entrar");
  });

  it("after too many attempts it refuses the email and offers Redefinir senha", async () => {
    respond("POST", SIGN_IN, { status: 429, body: { error: "too_many_attempts", message: "locked" } });
    renderAuth("/entrar");

    await signIn("antonio@segura.com.br", "errada-mesmo");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Muitas tentativas. Tente de novo em 15 minutos ou redefina a senha.");
    expect(screen.getByRole("link", { name: "redefina a senha" })).toHaveAttribute("href", "/redefinir-senha");
    expect(screen.getByRole("button", { name: "Entrar" })).toBeDisabled();
  });

  it("goes to the page in next once signed in", async () => {
    respond("POST", SIGN_IN, { body: {} });
    const router = renderAuth("/entrar?next=%2Fkbs%2Fkb-1%2Fn%2Frenovacao");

    await signIn("antonio@segura.com.br", "correto-cavalo");

    expect(await screen.findByText("Dentro")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/kbs/kb-1/n/renovacao");
    expect(calls.find((call) => call.path === SIGN_IN)?.body).toEqual({ email: "antonio@segura.com.br", password: "correto-cavalo" });
  });

  it("a next on another site is ignored", async () => {
    respond("POST", SIGN_IN, { body: {} });
    const router = renderAuth("/entrar?next=%2F%2Fexample.com");

    await signIn("antonio@segura.com.br", "correto-cavalo");

    expect(await screen.findByText("Dentro")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/bases");
  });
});
