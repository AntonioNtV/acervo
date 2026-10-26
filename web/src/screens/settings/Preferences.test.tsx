import "@testing-library/jest-dom/vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, renderWithApi, resetApi, respond } from "../../api/testing";
import { ThemeProvider } from "../../app/theme";
import { Preferences } from "./Preferences";
import { signedIn } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

beforeEach(() => {
  localStorage.clear();
  resetApi();
  document.documentElement.classList.remove("dark");
});

describe("Preferences", () => {
  it("a theme saves on the account at once and applies here", async () => {
    const account = signedIn();
    respond("PUT", "/v1/account/preferences", (_url, body) => ({ body: { ...account, preferences: body } }));
    renderWithApi(
      <ThemeProvider>
        <Preferences />
      </ThemeProvider>,
    );

    await userEvent.click(await screen.findByRole("button", { name: "Tema" }));
    await userEvent.click(await screen.findByRole("menuitemradio", { name: "Escuro" }));

    await waitFor(() =>
      expect(calls.find((call) => call.method === "PUT")).toMatchObject({
        path: "/v1/account/preferences",
        body: { theme: "dark", page_width: "default", language: "pt-BR", start_page: "last" },
      }),
    );
    expect(document.documentElement).toHaveClass("dark");
    expect(screen.getByRole("button", { name: "Tema" })).toHaveTextContent("Escuro");
  });
});
