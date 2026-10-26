import "@testing-library/jest-dom/vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, renderWithApi, resetApi, respond } from "../../api/testing";
import { Profile } from "./Profile";
import { signedIn } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

beforeEach(() => {
  localStorage.clear();
  resetApi();
});

describe("Profile", () => {
  it("refuses a photo over 2 MB before sending it", async () => {
    signedIn();
    renderWithApi(<Profile />);

    const photo = new File([new Uint8Array(3 * 1024 * 1024)], "foto.png", { type: "image/png" });
    await userEvent.upload(await screen.findByLabelText("Foto"), photo);

    expect(screen.getByRole("alert")).toHaveTextContent("A imagem tem 3 MB. Envie uma de até 2 MB.");
    expect(calls.some((call) => call.path === "/v1/account/photo")).toBe(false);
  });

  it("Remover goes back to the initials", async () => {
    const account = signedIn({ photo_url: "/v1/accounts/acc-1/photo?v=abc" });
    respond("DELETE", "/v1/account/photo", { body: { ...account, photo_url: null } });
    const { container } = renderWithApi(<Profile />);

    await userEvent.click(await screen.findByRole("button", { name: "Remover" }));

    expect(await screen.findByText("AB")).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
    expect(screen.queryByRole("button", { name: "Remover" })).not.toBeInTheDocument();
  });

  it("changes the email only once the code sent to the new one is typed", async () => {
    const account = signedIn();
    respond("POST", "/v1/account/email", { status: 202, body: {} });
    respond("POST", "/v1/account/email/confirm", (_url, body) =>
      (body as { code: string }).code === "482913"
        ? { body: { ...account, email: "antonio@novo.com.br" } }
        : { status: 422, body: { error: "code_invalid", message: "no" } },
    );
    renderWithApi(<Profile />);

    const email = await screen.findByLabelText("Email");
    await userEvent.clear(email);
    await userEvent.type(email, "antonio@novo.com.br");
    await userEvent.click(screen.getByRole("button", { name: "Enviar código" }));

    expect(await screen.findByText(/Enviamos um código para antonio@novo.com.br/)).toBeInTheDocument();
    expect(calls.find((call) => call.path === "/v1/account/email")?.body).toEqual({ new_email: "antonio@novo.com.br" });
    await userEvent.type(screen.getByLabelText("Código de 6 dígitos"), "111111");
    expect(await screen.findByRole("alert")).toHaveTextContent("Código incorreto ou vencido.");

    await userEvent.clear(screen.getByLabelText("Código de 6 dígitos"));
    await userEvent.type(screen.getByLabelText("Código de 6 dígitos"), "482913");

    await waitFor(() => expect(screen.getByLabelText("Email")).toHaveValue("antonio@novo.com.br"));
  });

  it("without a recent sign-in it asks the password, then sends the code", async () => {
    signedIn();
    let recent = false;
    respond("POST", "/v1/account/email", () =>
      recent ? { status: 204, body: undefined } : { status: 403, body: { error: "reauthentication_required", message: "no" } },
    );
    respond("POST", "/v1/sessions/reauthenticate", () => {
      recent = true;
      return { status: 204, body: undefined };
    });
    renderWithApi(<Profile />);

    const email = await screen.findByLabelText("Email");
    await userEvent.clear(email);
    await userEvent.type(email, "antonio@novo.com.br");
    await userEvent.click(screen.getByRole("button", { name: "Enviar código" }));
    await userEvent.type(await screen.findByLabelText("Senha"), "correto-cavalo");
    await userEvent.click(screen.getByRole("button", { name: "Confirmar" }));

    expect(await screen.findByText(/Enviamos um código para antonio@novo.com.br/)).toBeInTheDocument();
    expect(calls.find((call) => call.path === "/v1/sessions/reauthenticate")?.body).toEqual({ password: "correto-cavalo" });
  });
});
