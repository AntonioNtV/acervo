import "@testing-library/jest-dom/vitest";
import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, resetApi, respond } from "../../testing";
import { pageNode, renderPage, typeInSource, versions } from "./testing";

vi.mock("../../api/client", () => import("../../testing").then((m) => m.mockClient()));

const draft = { markdown: "## Documentos\n- Segunda via\n", base_version_id: "v2", updated_at: "2026-10-22T09:52:00Z" };
const puts = (path: string) => calls.filter((call) => call.method === "PUT" && call.path === path);

beforeEach(() => {
  localStorage.clear();
  resetApi();
  respond("GET", "/nodes/page-1/versions", { body: versions });
  respond("PUT", "/nodes/page-1/draft", { body: draft });
  respond("PUT", "/nodes/page-1", { body: versions[0] });
});

afterEach(() => vi.useRealTimers());

async function startEditing() {
  await userEvent.click(await screen.findByRole("button", { name: "Editar" }));
  // The autosave's pause is then counted by the test.
  vi.useFakeTimers({ shouldAdvanceTime: true });
  typeInSource("- Boleto no portal\n");
}

describe("PageView", () => {
  it("Ler renders a resolved and a missing wiki link", async () => {
    respond("GET", "/nodes/page-1", {
      body: pageNode({
        markdown: "Ver [[Renovação]] e [[Sinistros]].",
        links: { "renovação": "page-2", sinistros: "missing" },
      }),
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
    respond("GET", "/nodes/page-1", { body: pageNode({ draft }) });
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: "Continuar rascunho" }));
    expect(screen.getByRole("button", { name: "Editar" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "Concluir" }));

    await waitFor(() =>
      expect(puts("/nodes/page-1").at(-1)?.body).toEqual({ markdown: draft.markdown, base_version_id: "v2", force: false }),
    );
    expect(await screen.findByRole("button", { name: "Ler" })).toHaveAttribute("aria-pressed", "true");
  });

  it("autosave sends the draft after the pause", async () => {
    respond("GET", "/nodes/page-1", { body: pageNode() });
    renderPage();
    await startEditing();

    await act(() => vi.advanceTimersByTimeAsync(1000));
    expect(puts("/nodes/page-1/draft")).toHaveLength(0);
    await act(() => vi.advanceTimersByTimeAsync(1100));

    await waitFor(() =>
      expect(puts("/nodes/page-1/draft").at(-1)?.body).toEqual({
        markdown: "## Documentos\n- Boleto no portal\n",
        base_version_id: "v2",
      }),
    );
  });

  it("leaving with changes saves a version", async () => {
    respond("GET", "/nodes/page-1", { body: pageNode() });
    const { unmount } = renderPage();
    await startEditing();

    unmount();

    await waitFor(() =>
      expect(puts("/nodes/page-1").at(-1)?.body).toEqual({
        markdown: "## Documentos\n- Boleto no portal\n",
        base_version_id: "v2",
        force: false,
      }),
    );
    expect(puts("/nodes/page-1/draft")).toHaveLength(0);
  });

  it("a 409 on the leave-save falls back to the draft", async () => {
    respond("GET", "/nodes/page-1", { body: pageNode() });
    respond("PUT", "/nodes/page-1", {
      status: 409,
      body: { error: "ConflictError", message: "page page-1 changed", detail: { current_version_id: "v3", markdown: "", diff: [] } },
    });
    const { unmount } = renderPage();
    await startEditing();

    unmount();

    await waitFor(() =>
      expect(puts("/nodes/page-1/draft").at(-1)?.body).toEqual({
        markdown: "## Documentos\n- Boleto no portal\n",
        base_version_id: "v2",
      }),
    );
  });

  it("typing while a draft offer is unanswered does not overwrite it", async () => {
    respond("GET", "/nodes/page-1", { body: pageNode({ draft }) });
    const { unmount } = renderPage();
    await screen.findByRole("button", { name: "Continuar rascunho" });
    await startEditing();

    await act(() => vi.advanceTimersByTimeAsync(5000));
    expect(screen.getByRole("button", { name: "Continuar rascunho" })).toBeInTheDocument();
    unmount();
    await act(() => vi.advanceTimersByTimeAsync(5000));

    expect(puts("/nodes/page-1/draft")).toHaveLength(0);
    expect(puts("/nodes/page-1")).toHaveLength(0);
  });
});
