import "@testing-library/jest-dom/vitest";
import { screen, waitFor, within } from "@testing-library/react";
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

describe("History", () => {
  it("lists versions and restores one", async () => {
    const restore = vi.fn(() => pageNode());
    serve(fetchMock, {
      "GET /nodes/page-1": pageNode(),
      "GET /nodes/page-1/versions": versions,
      "POST /nodes/page-1/versions/v1/restore": restore,
    });
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: "Histórico" }));
    const panel = screen.getByRole("complementary", { name: "Histórico" });
    expect(await within(panel).findByText("Versão 2 · atual")).toBeInTheDocument();
    expect(within(panel).getByText("Versão 1")).toBeInTheDocument();
    expect(within(panel).getAllByText("você")).toHaveLength(2);
    expect(within(panel).getAllByRole("button", { name: "Restaurar anterior" })).toHaveLength(1);

    await userEvent.click(within(panel).getByRole("button", { name: "Restaurar anterior" }));
    await waitFor(() => expect(restore).toHaveBeenCalledTimes(1));
  });
});
