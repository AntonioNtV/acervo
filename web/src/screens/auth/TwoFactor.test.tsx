import "@testing-library/jest-dom/vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, resetApi, respond } from "../../api/testing";
import { renderAuth } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

beforeEach(() => {
  localStorage.clear();
  resetApi();
  respond("POST", "/v1/auth/sign-in", {
    body: { pending: true, method: "whatsapp", destination: "+55 •• ••••-4821" },
  });
});

async function signIn() {
  await userEvent.type(screen.getByLabelText("Email"), "antonio@segura.com.br");
  await userEvent.type(screen.getByLabelText("Senha"), "correto-cavalo");
  await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
}

describe("TwoFactor", () => {
  it("a password sign-in with two-step verification asks the code, and the right one goes to next", async () => {
    respond("POST", "/v1/auth/two-factor", (_url, body) =>
      (body as { code: string }).code === "482913"
        ? { body: {} }
        : { status: 422, body: { error: "code_invalid", message: "no" } },
    );
    const router = renderAuth("/entrar?next=%2Fkbs%2Fkb-1");

    await signIn();

    expect(await screen.findByText("Enviamos um código para o seu WhatsApp +55 •• ••••-4821.")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Código de 6 dígitos"), "111111");
    expect(await screen.findByRole("alert")).toHaveTextContent("Código incorreto ou vencido.");

    await userEvent.clear(screen.getByLabelText("Código de 6 dígitos"));
    await userEvent.type(screen.getByLabelText("Código de 6 dígitos"), "482913");

    expect(await screen.findByText("Dentro")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/kbs/kb-1");
  });

  it("Receber por email sends the code to the account email instead", async () => {
    respond("POST", "/v1/auth/two-factor/resend", {
      body: { pending: true, method: "email", destination: "a••••@segura.com.br" },
    });
    renderAuth("/entrar");

    await signIn();
    await userEvent.click(await screen.findByRole("button", { name: "Receber por email" }));

    expect(await screen.findByText("Enviamos um código para a••••@segura.com.br.")).toBeInTheDocument();
    expect(calls.find((call) => call.path === "/v1/auth/two-factor/resend")?.body).toEqual({ channel: "email" });
    expect(screen.queryByRole("button", { name: "Receber por email" })).not.toBeInTheDocument();
  });
});
