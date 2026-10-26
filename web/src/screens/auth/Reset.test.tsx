import "@testing-library/jest-dom/vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { resetApi, respond } from "../../api/testing";
import { renderAuth } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

beforeEach(() => {
  localStorage.clear();
  resetApi();
});

describe("Reset", () => {
  it.each(["antonio@segura.com.br", "ninguem@segura.com.br"])(
    "the link sent says the same whether or not %s has an account",
    async (email) => {
      respond("POST", "/v1/auth/reset", { status: 204, body: undefined });
      renderAuth("/redefinir-senha");

      await userEvent.type(screen.getByLabelText("Email"), email);
      await userEvent.click(screen.getByRole("button", { name: "Enviar link" }));

      expect(await screen.findByRole("heading", { name: "Confira seu email" })).toBeInTheDocument();
      expect(
        screen.getByText(`Se existir uma conta para ${email}, o link chega em alguns minutos. Ele vale por 1 hora.`),
      ).toBeInTheDocument();
    },
  );

  it("an expired or used link says so and offers another", async () => {
    respond("POST", "/v1/auth/reset/confirm", { status: 422, body: { error: "code_invalid", message: "expired" } });
    renderAuth("/redefinir-senha/token-1");

    await userEvent.type(screen.getByLabelText("Nova senha"), "correto-cavalo");
    await userEvent.type(screen.getByLabelText("Repita a nova senha"), "correto-cavalo");
    await userEvent.click(screen.getByRole("button", { name: "Salvar e entrar" }));

    expect(await screen.findByRole("heading", { name: "Link vencido" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Pedir outro link" })).toHaveAttribute("href", "/redefinir-senha");
  });
});
