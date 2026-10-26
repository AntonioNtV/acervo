import "@testing-library/jest-dom/vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, renderWithApi, resetApi, respond } from "../../api/testing";
import type { Session } from "../../data/sessions";
import Sessions from "./Sessions";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

beforeEach(() => {
  localStorage.clear();
  resetApi();
});

function session(id: string, browser: string, system: string, current = false): Session {
  const now = new Date().toISOString();
  return { id, browser, system, current, method: "password", created_at: now, last_seen_at: now };
}

/** This Chrome on a Mac, and Safari on an iPhone. */
function renderSessions() {
  respond("GET", "/v1/sessions", {
    body: [session("s-1", "Chrome", "macOS", true), session("s-2", "Safari", "iPhone")],
  });
  renderWithApi(<Sessions />);
}

const row = async (text: string) => (await screen.findByText(text)).closest<HTMLElement>(".border-b")!;

describe("Sessions", () => {
  it("ends another session", async () => {
    renderSessions();
    respond("DELETE", "/v1/sessions/s-2", { status: 204, body: undefined });

    expect(within(await row("Chrome no macOS")).getByText("Este aparelho")).toBeInTheDocument();
    await userEvent.click(within(await row("Safari no iPhone")).getByRole("button", { name: "Encerrar" }));

    await waitFor(() =>
      expect(calls.some((call) => call.method === "DELETE" && call.path === "/v1/sessions/s-2")).toBe(true),
    );
  });

  it("ends every other session", async () => {
    renderSessions();
    respond("POST", "/v1/sessions/end-others", { status: 204, body: undefined });

    await userEvent.click(await screen.findByRole("button", { name: "Sair de todas as outras" }));

    await waitFor(() => expect(calls.some((call) => call.path === "/v1/sessions/end-others")).toBe(true));
  });
});
