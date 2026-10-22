import "@testing-library/jest-dom/vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, resetApi, respond } from "../../api/testing";
import { pageNode, renderPage, versions } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

beforeEach(() => {
  localStorage.clear();
  resetApi();
});

describe("Conflict", () => {
  it("a stale_page opens the dialog with the diff and Manter a minha sends force", async () => {
    const mine = "## Documentos\n- Segunda via\n";
    respond("GET", "/v1/nodes/page-1", {
      body: pageNode({ draft: { markdown: mine, base_version_id: "v2", updated_at: "2026-10-22T09:52:00Z" } }),
    });
    respond("GET", "/v1/pages/page-1/versions", { body: versions });
    respond("PUT", "/v1/pages/page-1", (_url, body) =>
      (body as { force: boolean }).force
        ? { body: versions[0] }
        : {
            status: 409,
            body: {
              error: "stale_page",
              message: "page page-1 changed",
              details: {
                current_version_id: "v3",
                markdown: "## Documentos\n- Boleto no portal\n",
                diff: [
                  { op: "same", text: "## Documentos" },
                  { op: "add", text: "- Boleto no portal" },
                ],
              },
            },
          },
    );
    const saves = () => calls.filter((call) => call.method === "PUT" && call.path === "/v1/pages/page-1");
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: "Continuar rascunho" }));
    await userEvent.click(screen.getByRole("button", { name: "Concluir" }));

    const dialog = await screen.findByRole("dialog", { name: "Esta página mudou desde que você abriu" });
    expect(within(dialog).getByText(/Boleto no portal/)).toHaveAttribute("data-op", "add");

    await userEvent.click(within(dialog).getByRole("button", { name: "Manter a minha" }));
    await waitFor(() => expect(saves().at(-1)?.body).toEqual({ markdown: mine, base_version_id: "v3", force: true }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
