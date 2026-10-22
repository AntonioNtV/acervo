import "@testing-library/jest-dom/vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { json, pageNode, renderPage, serve, versions } from "./testing";

const fetchMock = vi.hoisted(() => {
  const fn = vi.fn<(request: Request) => Promise<Response>>();
  globalThis.fetch = fn as unknown as typeof fetch;
  return fn;
});

beforeEach(() => {
  localStorage.clear();
  fetchMock.mockReset();
});

describe("Conflict", () => {
  it("a 409 opens the dialog with the diff and Manter a minha sends force", async () => {
    const mine = "## Documentos\n- Segunda via\n";
    const save = vi.fn((body: unknown) =>
      (body as { force: boolean }).force
        ? versions[0]
        : json(409, {
            error: "ConflictError",
            message: "page page-1 changed",
            detail: {
              current_version_id: "v3",
              markdown: "## Documentos\n- Boleto no portal\n",
              diff: [
                { op: "same", text: "## Documentos" },
                { op: "add", text: "- Boleto no portal" },
              ],
            },
          }),
    );
    serve(fetchMock, {
      "GET /nodes/page-1": pageNode({
        draft: { markdown: mine, base_version_id: "v2", updated_at: "2026-10-22T09:52:00Z" },
      }),
      "GET /nodes/page-1/versions": versions,
      "PUT /nodes/page-1": save,
    });
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: "Continuar rascunho" }));
    await userEvent.click(screen.getByRole("button", { name: "Concluir" }));

    const dialog = await screen.findByRole("dialog", { name: "Esta página mudou desde que você abriu" });
    expect(within(dialog).getByText(/Boleto no portal/)).toHaveAttribute("data-op", "add");

    await userEvent.click(within(dialog).getByRole("button", { name: "Manter a minha" }));
    await waitFor(() => expect(save).toHaveBeenLastCalledWith({ markdown: mine, base_version_id: "v3", force: true }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
