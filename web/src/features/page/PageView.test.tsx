import "@testing-library/jest-dom/vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { pageNode, renderPage, serve, versions } from "./testing";

const fetchMock = vi.hoisted(() => {
  const fn = vi.fn<(request: Request) => Promise<Response>>();
  globalThis.fetch = fn as unknown as typeof fetch;
  return fn;
});

beforeEach(() => {
  localStorage.clear();
  fetchMock.mockReset();
});

describe("PageView", () => {
  it("Ler renders a resolved and a missing wiki link", async () => {
    serve(fetchMock, {
      "GET /nodes/page-1": pageNode({
        markdown: "Ver [[Renovação]] e [[Sinistros]].",
        links: { "renovação": "page-2", sinistros: "missing" },
      }),
      "GET /nodes/page-1/versions": versions,
    });
    renderPage();

    const resolved = await screen.findByRole("link", { name: "Renovação" });
    expect(resolved).toHaveAttribute("href", "/kbs/kb-1/n/page-2");
    const missing = screen.getByText("Sinistros");
    expect(missing.closest("a")).toBeNull();
    expect(missing).toHaveClass("text-ghost");
    expect(missing).toHaveAttribute("title", "Nenhuma página com esse nome");
  });

  it("Concluir calls save", async () => {
    const save = vi.fn(() => versions[0]);
    serve(fetchMock, {
      "GET /nodes/page-1": pageNode({
        draft: { markdown: "## Documentos\n- Segunda via\n", base_version_id: "v2", updated_at: "2026-10-22T09:52:00Z" },
      }),
      "GET /nodes/page-1/versions": versions,
      "PUT /nodes/page-1": save,
    });
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: "Continuar rascunho" }));
    expect(screen.getByRole("button", { name: "Editar" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "Concluir" }));

    await waitFor(() =>
      expect(save).toHaveBeenCalledWith({ markdown: "## Documentos\n- Segunda via\n", base_version_id: "v2", force: false }),
    );
    expect(await screen.findByRole("button", { name: "Ler" })).toHaveAttribute("aria-pressed", "true");
  });
});
