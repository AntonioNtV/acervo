import "@testing-library/jest-dom/vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, renderWithApi, resetApi, respond } from "../../api/testing";
import { ThemeProvider } from "../../app/theme";
import { Notifications } from "./Notifications";
import { signedIn } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

beforeEach(() => {
  localStorage.clear();
  resetApi();
});

describe("Notifications", () => {
  it("a toggle saves on the account with every other preference", async () => {
    const account = signedIn();
    respond("PUT", "/v1/account/preferences", (_url, body) => ({ body: { ...account, preferences: body } }));
    renderWithApi(
      <ThemeProvider>
        <Notifications />
      </ThemeProvider>,
    );

    expect(await screen.findByText("Enviados para antonio@segura.com.br.")).toBeInTheDocument();
    expect(screen.getByText("Sempre")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: "Convites e acessos" }));

    await waitFor(() =>
      expect(calls.find((call) => call.method === "PUT")?.body).toEqual({
        ...account.preferences,
        notify_invites: false,
      }),
    );
    expect(screen.getByRole("checkbox", { name: "Convites e acessos" })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Mudanças nas páginas que você segue" })).not.toBeChecked();
  });
});
