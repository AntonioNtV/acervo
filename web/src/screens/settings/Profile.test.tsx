import "@testing-library/jest-dom/vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { calls, renderWithApi, resetApi, respond } from "../../api/testing";
import { ThemeProvider } from "../../app/theme";
import { Profile } from "./Profile";
import { signedIn } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

beforeEach(() => {
  localStorage.clear();
  resetApi();
});

function renderProfile() {
  return renderWithApi(
    <ThemeProvider>
      <MemoryRouter initialEntries={["/conta/perfil"]}>
        <Routes>
          <Route path="/conta/perfil" element={<Profile />} />
          <Route path="/entrar" element={<p>Entrar</p>} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

describe("Profile", () => {
  it("refuses a photo over 2 MB before sending it", async () => {
    signedIn();
    renderProfile();

    const photo = new File([new Uint8Array(3 * 1024 * 1024)], "foto.png", { type: "image/png" });
    await userEvent.upload(await screen.findByLabelText("Foto"), photo);

    expect(screen.getByRole("alert")).toHaveTextContent("A imagem tem 3 MB. Envie uma de até 2 MB.");
    expect(calls.some((call) => call.path === "/v1/account/photo")).toBe(false);
  });

  it("Remover goes back to the initials", async () => {
    const account = signedIn({ photo_url: "/v1/accounts/acc-1/photo?v=abc" });
    respond("DELETE", "/v1/account/photo", { body: { ...account, photo_url: null } });
    const { container } = renderProfile();

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
    renderProfile();

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
    renderProfile();

    const email = await screen.findByLabelText("Email");
    await userEvent.clear(email);
    await userEvent.type(email, "antonio@novo.com.br");
    await userEvent.click(screen.getByRole("button", { name: "Enviar código" }));
    await userEvent.type(await screen.findByLabelText("Senha"), "correto-cavalo");
    await userEvent.click(screen.getByRole("button", { name: "Confirmar" }));

    expect(await screen.findByText(/Enviamos um código para antonio@novo.com.br/)).toBeInTheDocument();
    expect(calls.find((call) => call.path === "/v1/sessions/reauthenticate")?.body).toEqual({ password: "correto-cavalo" });
  });

  it("Excluir conta names the organizations that go, asks the password again and lands on Entrar", async () => {
    signedIn();
    const org = { logo_url: null, new_base_access: "editor", require_two_factor: false, personal: false } as const;
    respond("GET", "/v1/organizations", {
      body: [
        { ...org, id: "pessoal", name: "Pessoal", my_role: "owner", personal: true },
        { ...org, id: "org-1", name: "Escritório Lima", my_role: "owner" },
        { ...org, id: "org-2", name: "Seguros SA", my_role: "member" },
      ],
    });
    respond("GET", "/v1/organizations/org-1/members", {
      body: [{ account_id: "acc-1", name: "Antonio Bertino", email: "antonio@segura.com.br", photo_url: null, role: "owner" }],
    });
    let recent = false;
    respond("DELETE", "/v1/account", () =>
      recent ? { status: 204, body: undefined } : { status: 403, body: { error: "reauthentication_required", message: "no" } },
    );
    respond("POST", "/v1/sessions/reauthenticate", () => {
      recent = true;
      return { status: 204, body: undefined };
    });
    renderProfile();

    await userEvent.click(await screen.findByRole("button", { name: "Excluir conta" }));
    const dialog = await screen.findByRole("dialog", { name: "Excluir sua conta" });
    expect(await within(dialog).findByText(/Você é o único Owner de Escritório Lima/)).toBeInTheDocument();
    expect(within(dialog).getByText("Você sai de Seguros SA.")).toBeInTheDocument();
    await userEvent.type(within(dialog).getByLabelText("Digite antonio@segura.com.br para confirmar"), "antonio@segura.com.br");
    await userEvent.click(within(dialog).getByRole("button", { name: "Excluir conta" }));
    await userEvent.type(await screen.findByLabelText("Senha"), "correto-cavalo");
    await userEvent.click(screen.getByRole("button", { name: "Confirmar" }));

    expect(await screen.findByText("Entrar")).toBeInTheDocument();
    expect(calls.filter((call) => call.method === "DELETE" && call.path === "/v1/account")).toHaveLength(2);
  });
});
