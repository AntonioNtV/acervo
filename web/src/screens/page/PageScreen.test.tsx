import "@testing-library/jest-dom/vitest";
import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, resetApi, respond } from "../../api/testing";
import { pageNode, renderPage, typeInPage } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

const textPuts = () => calls.filter((call) => call.method === "PUT" && call.path === "/v1/pages/page-1/text");

beforeEach(() => {
  localStorage.clear();
  resetApi();
  respond("GET", "/v1/nodes/page-1", { body: pageNode() });
  respond("PUT", "/v1/pages/page-1/text", (_url, body) => ({
    body: { revision: (body as { revision: number }).revision + 1, saved_at: "2026-10-22T10:00:00Z" },
  }));
  respond("POST", "/v1/pages/page-1/leave", { status: 204, body: "" });
});

afterEach(() => vi.useRealTimers());

async function openPage() {
  const rendered = renderPage();
  await screen.findByRole("textbox", { name: "Texto da página" });
  // The pauses are then counted by the test.
  vi.useFakeTimers({ shouldAdvanceTime: true });
  return rendered;
}

describe("PageScreen", () => {
  it("typing saves once after the pause, with the revision", async () => {
    await openPage();

    typeInPage("Boleto");
    await act(() => vi.advanceTimersByTimeAsync(500));
    typeInPage("no portal");
    expect(screen.getByText("Salvando…")).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(900));
    expect(textPuts()).toHaveLength(0);
    await act(() => vi.advanceTimersByTimeAsync(200));

    await waitFor(() => expect(textPuts()).toHaveLength(1));
    expect(textPuts()[0]!.body).toEqual({ markdown: "## Documentos\n\nBoleto\n\nno portal\n", revision: 4 });
    expect(await screen.findByText("Salvo")).toBeInTheDocument();
  });

  it("a stale_page reloads the newest text and says so", async () => {
    respond("PUT", "/v1/pages/page-1/text", {
      status: 409,
      body: {
        error: "stale_page",
        message: "page page-1 changed since revision 4",
        details: { markdown: "## Documentos\n\n- Boleto no portal\n", revision: 7 },
      },
    });
    await openPage();

    typeInPage("Segunda via");
    await act(() => vi.advanceTimersByTimeAsync(1100));

    expect(await screen.findByRole("status")).toHaveTextContent("Esta página mudou em outra aba");
    expect(screen.getByText("Boleto no portal")).toBeInTheDocument();
    expect(screen.queryByText("Segunda via")).not.toBeInTheDocument();

    respond("PUT", "/v1/pages/page-1/text", { body: { revision: 8, saved_at: "2026-10-22T10:00:00Z" } });
    typeInPage("Apólice");
    await act(() => vi.advanceTimersByTimeAsync(1100));
    await waitFor(() => expect(textPuts().at(-1)?.body).toMatchObject({ revision: 7 }));
  });

  it("leaving or hiding the tab saves what is pending and calls leave", async () => {
    const leaves = () => calls.filter((call) => call.path === "/v1/pages/page-1/leave");
    const { unmount } = await openPage();

    Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
    act(() => void document.dispatchEvent(new Event("visibilitychange")));
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
    await waitFor(() => expect(leaves()).toHaveLength(1));

    typeInPage("Boleto");
    unmount();

    await waitFor(() => expect(leaves()).toHaveLength(2));
    expect(textPuts()).toHaveLength(1);
    const order = calls.map((call) => call.path).filter((path) => path.startsWith("/v1/pages/"));
    expect(order.slice(-2)).toEqual(["/v1/pages/page-1/text", "/v1/pages/page-1/leave"]);
  });

  it("the title renames the node after the pause", async () => {
    respond("PATCH", "/v1/nodes/page-1", { body: { ...pageNode(), title: "Emissão da apólice" } });
    await openPage();
    const title = screen.getByRole("textbox", { name: "Título da página" });

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    await user.clear(title);
    await user.type(title, "Emissão da apólice");
    expect(calls.filter((call) => call.method === "PATCH")).toHaveLength(0);
    await act(() => vi.advanceTimersByTimeAsync(1100));

    await waitFor(() =>
      expect(calls.filter((call) => call.method === "PATCH" && call.path === "/v1/nodes/page-1")).toEqual([
        expect.objectContaining({ body: { title: "Emissão da apólice" } }),
      ]),
    );
  });
});
