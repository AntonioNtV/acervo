import "@testing-library/jest-dom/vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, resetApi, respond } from "../../testing";
import { pageNode, renderPage, versions } from "./testing";

vi.mock("../../api/client", () => import("../../testing").then((m) => m.mockClient()));

beforeEach(() => {
  localStorage.clear();
  resetApi();
});

describe("History", () => {
  it("lists versions and restores one", async () => {
    respond("GET", "/nodes/page-1", { body: pageNode() });
    respond("GET", "/nodes/page-1/versions", { body: versions });
    respond("POST", "/nodes/page-1/versions/v1/restore", { body: pageNode() });
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: "Histórico" }));
    const panel = screen.getByRole("complementary", { name: "Histórico" });
    expect(await within(panel).findByText("Versão 2 · atual")).toBeInTheDocument();
    expect(within(panel).getByText("Versão 1")).toBeInTheDocument();
    expect(within(panel).getAllByText("você")).toHaveLength(2);
    expect(within(panel).getAllByRole("button", { name: "Restaurar anterior" })).toHaveLength(1);

    await userEvent.click(within(panel).getByRole("button", { name: "Restaurar anterior" }));
    await waitFor(() =>
      expect(calls.filter((call) => call.path === "/nodes/page-1/versions/v1/restore")).toHaveLength(1),
    );
  });
});
