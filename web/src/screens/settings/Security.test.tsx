import "@testing-library/jest-dom/vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, renderWithApi, resetApi, respond } from "../../api/testing";
import { Security } from "./Security";
import { signedIn } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

const bytes = (...values: number[]) => new Uint8Array(values).buffer;

beforeEach(() => {
  localStorage.clear();
  resetApi();
  respond("GET", "/v1/organizations", { body: [] });
  respond("GET", "/v1/passkeys", { body: [] });
});

describe("Security", () => {
  it("Adicionar passkey runs the browser's prompt with the API's options and keeps what it made", async () => {
    signedIn();
    respond("POST", "/v1/passkeys/register/options", {
      body: {
        options: {
          challenge: "AQID",
          rp: { id: "localhost", name: "Acervo" },
          user: { id: "BAUG", name: "antonio@segura.com.br", displayName: "Antonio Bertino" },
          pubKeyCredParams: [{ type: "public-key", alg: -7 }],
          excludeCredentials: [],
        },
      },
    });
    respond("POST", "/v1/passkeys/register", {
      status: 201,
      body: { id: "pk-1", name: "1Password", created_at: "2026-10-12T10:00:00Z", last_used_at: null },
    });
    const create = vi.fn().mockResolvedValue({
      id: "Bwg",
      rawId: bytes(7, 8),
      type: "public-key",
      authenticatorAttachment: "platform",
      getClientExtensionResults: () => ({}),
      response: { clientDataJSON: bytes(9), attestationObject: bytes(10), getTransports: () => ["internal"] },
    });
    Object.defineProperty(navigator, "credentials", { configurable: true, value: { create } });
    renderWithApi(<Security />);

    await userEvent.click(await screen.findByRole("button", { name: "Adicionar passkey" }));

    await waitFor(() => expect(calls.some((call) => call.path === "/v1/passkeys/register")).toBe(true));
    const publicKey = create.mock.calls[0]![0].publicKey;
    expect(new Uint8Array(publicKey.challenge)).toEqual(new Uint8Array([1, 2, 3]));
    expect(new Uint8Array(publicKey.user.id)).toEqual(new Uint8Array([4, 5, 6]));
    expect(calls.find((call) => call.path === "/v1/passkeys/register")?.body).toEqual({
      credential: {
        id: "Bwg",
        rawId: "Bwg",
        type: "public-key",
        authenticatorAttachment: "platform",
        clientExtensionResults: {},
        response: { clientDataJSON: "CQ", attestationObject: "Cg", transports: ["internal"] },
      },
    });
  });

  it("Desativar without a recent sign-in asks the password, then turns two-step verification off", async () => {
    const account = signedIn({ two_factor: "email" });
    let recent = false;
    respond("DELETE", "/v1/two-factor", () =>
      recent
        ? { body: { ...account, two_factor: "none" } }
        : { status: 403, body: { error: "reauthentication_required", message: "no" } },
    );
    respond("POST", "/v1/sessions/reauthenticate", () => {
      recent = true;
      return { status: 204, body: undefined };
    });
    renderWithApi(<Security />);

    await userEvent.click(await screen.findByRole("button", { name: "Desativar" }));

    expect(await screen.findByRole("dialog", { name: "Confirme que é você" })).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Senha"), "correto-cavalo");
    await userEvent.click(screen.getByRole("button", { name: "Confirmar" }));

    await waitFor(() => expect(screen.queryByRole("button", { name: "Desativar" })).not.toBeInTheDocument());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(calls.filter((call) => call.path === "/v1/two-factor").length).toBe(2);
  });
});
