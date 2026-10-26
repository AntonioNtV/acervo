import "@testing-library/jest-dom/vitest";
import { act, fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, resetApi, respond } from "../../api/testing";
import { renderAuth } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

beforeEach(() => {
  localStorage.clear();
  resetApi();
});

afterEach(() => {
  vi.useRealTimers();
});

async function signUp(email: string) {
  await userEvent.type(screen.getByLabelText("Nome"), "Antonio Bertino");
  await userEvent.type(screen.getByLabelText("Email"), email);
  await userEvent.type(screen.getByLabelText("Senha"), "correto-cavalo");
  await userEvent.click(screen.getByRole("button", { name: "Criar conta" }));
}

describe("SignUp", () => {
  it("says the email already has an account, with a link to Entrar", async () => {
    respond("POST", "/v1/auth/sign-up", { status: 409, body: { error: "email_taken", message: "taken" } });
    renderAuth("/criar-conta");

    await signUp("antonio@segura.com.br");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Já existe uma conta com este email. Entrar");
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
  });

  it("asks for the code sent to the email, and the right one signs in", async () => {
    respond("POST", "/v1/auth/sign-up", { status: 201, body: {} });
    respond("POST", "/v1/auth/verify-email", (_url, body) =>
      (body as { code: string }).code === "482913"
        ? { body: {} }
        : { status: 422, body: { error: "code_invalid", message: "no" } },
    );
    const router = renderAuth("/criar-conta");

    await signUp("antonio@segura.com.br");

    expect(await screen.findByRole("heading", { name: "Confirme seu email" })).toBeInTheDocument();
    expect(screen.getByText("Enviamos um código para a••••@segura.com.br.")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Código de 6 dígitos"), "111111");
    expect(await screen.findByRole("alert")).toHaveTextContent("Código incorreto ou vencido.");

    await userEvent.clear(screen.getByLabelText("Código de 6 dígitos"));
    await userEvent.type(screen.getByLabelText("Código de 6 dígitos"), "482913");

    expect(await screen.findByText("Dentro")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/bases");
    expect(calls.filter((call) => call.path === "/v1/auth/verify-email").at(-1)?.body).toEqual({
      email: "antonio@segura.com.br",
      code: "482913",
    });
  });

  it("offers a new code only after 60 s, and counts again after sending it", async () => {
    vi.useFakeTimers({ toFake: ["Date", "setInterval", "clearInterval"] });
    respond("POST", "/v1/auth/resend-code", { status: 204, body: undefined });
    renderAuth({ pathname: "/confirmar-email", state: { email: "antonio@segura.com.br" } });

    expect(await screen.findByText("Reenviar em 1:00")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(59_000));
    expect(screen.getByText("Reenviar em 0:01")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reenviar código" })).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1_000));

    fireEvent.click(screen.getByRole("button", { name: "Reenviar código" }));

    expect(await screen.findByText("Reenviar em 1:00")).toBeInTheDocument();
    expect(calls.find((call) => call.path === "/v1/auth/resend-code")?.body).toEqual({ email: "antonio@segura.com.br" });
  });
});
