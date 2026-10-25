import "@testing-library/jest-dom/vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, resetApi, respond } from "../../api/testing";
import { pageNode, renderPage, versions } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

beforeEach(() => {
  localStorage.clear();
  resetApi();
  respond("GET", "/v1/nodes/page-1", { body: pageNode() });
  respond("GET", "/v1/pages/page-1/versions", { body: versions });
  respond("POST", "/v1/pages/page-1/leave", { status: 204, body: "" });
});

async function openHistory() {
  renderPage();
  await userEvent.click(await screen.findByRole("button", { name: "Histórico" }));
  return screen.getByRole("complementary", { name: "Histórico" });
}

describe("History", () => {
  it("lists the editing sessions by day", async () => {
    const panel = await openHistory();

    const day = await within(panel).findByRole("region", { name: "14 de outubro" });
    const rows = within(day).getAllByRole("button");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("12 min de edição");
  });

  it("shows the selected version in the page with what came in and went out marked", async () => {
    respond("GET", "/v1/pages/page-1/versions/v2/diff", {
      body: {
        lines: [
          { op: "same", text: "## Documentos" },
          { op: "del", text: "- PDF da apólice no mesmo dia" },
          { op: "add", text: "- PDF da apólice, 3 dias depois" },
        ],
      },
    });
    const panel = await openHistory();

    await userEvent.click((await within(panel).findAllByRole("button", { pressed: false }))[0]!);

    expect((await screen.findByText("- PDF da apólice, 3 dias depois")).closest("[data-op]")).toHaveAttribute(
      "data-op",
      "add",
    );
    expect(screen.getByText("- PDF da apólice no mesmo dia").closest("[data-op]")).toHaveAttribute("data-op", "del");
    expect(screen.getByText(/Vendo a versão de/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Voltar à atual" }));
    expect(screen.queryByText("- PDF da apólice, 3 dias depois")).not.toBeInTheDocument();
  });

  it("restores the selected version and reopens the page on its text", async () => {
    respond("GET", "/v1/pages/page-1/versions/v1/diff", { body: { lines: [{ op: "add", text: "Texto antigo" }] } });
    respond("POST", "/v1/pages/page-1/versions/v1/restore", {
      body: { ...pageNode().page, markdown: "Texto antigo\n", revision: 9 },
    });
    const panel = await openHistory();

    const rows = await within(panel).findAllByRole("button", { pressed: false });
    await userEvent.click(rows[1]!);
    await userEvent.click(await screen.findByRole("button", { name: "Restaurar esta versão" }));

    await waitFor(() =>
      expect(calls.filter((call) => call.path === "/v1/pages/page-1/versions/v1/restore")).toHaveLength(1),
    );
    const editor = await screen.findByRole("textbox", { name: "Texto da página" });
    expect(within(editor).getByText("Texto antigo")).toBeInTheDocument();
    expect(screen.queryByText(/Vendo a versão de/)).not.toBeInTheDocument();
  });
});
