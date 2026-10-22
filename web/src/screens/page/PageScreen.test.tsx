import "@testing-library/jest-dom/vitest";
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, resetApi, respond } from "../../api/testing";
import { pageNode, renderPage, typeInPage } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

const textPuts = () => calls.filter((call) => call.method === "PUT" && call.path === "/v1/pages/page-1/text");
const leaves = () => calls.filter((call) => call.path === "/v1/pages/page-1/leave");
const pagePaths = () => calls.map((call) => call.path).filter((path) => path.startsWith("/v1/pages/"));

const saved = (body: unknown) => ({
  body: { revision: (body as { revision: number }).revision + 1, saved_at: "2026-10-22T10:00:00Z" },
});

/** Answers the next saves only when `release` is called, with what `answer` gives for each. */
function holdSaves(answer: (body: unknown) => { status?: number; body: unknown } = saved) {
  const waiting: Array<() => void> = [];
  respond(
    "PUT",
    "/v1/pages/page-1/text",
    (_url, body) => new Promise((resolve) => waiting.push(() => resolve(answer(body)))),
  );
  return async () => {
    await waitFor(() => expect(waiting.length).toBeGreaterThan(0));
    await act(async () => waiting.shift()!());
  };
}

function hideTab() {
  Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
  act(() => void document.dispatchEvent(new Event("visibilitychange")));
  Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
}

beforeEach(() => {
  localStorage.clear();
  resetApi();
  respond("GET", "/v1/nodes/page-1", { body: pageNode() });
  respond("PUT", "/v1/pages/page-1/text", (_url, body) => ({
    body: { revision: (body as { revision: number }).revision + 1, saved_at: "2026-10-22T10:00:00Z" },
  }));
  respond("POST", "/v1/pages/page-1/leave", { status: 204, body: "" });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

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
    const { unmount } = await openPage();

    typeInPage("Boleto");
    hideTab();
    await waitFor(() => expect(leaves()).toHaveLength(1));
    // The tab may be closing: both go out at once, and only keepalive requests outlive it.
    expect(textPuts().map((put) => put.keepalive)).toEqual([true]);
    expect(leaves()[0]!.keepalive).toBe(true);

    typeInPage("no portal");
    unmount();

    await waitFor(() => expect(leaves()).toHaveLength(2));
    // Leaving inside the app waits for the save, sent as a normal request.
    expect(textPuts().map((put) => put.keepalive)).toEqual([true, false]);
    expect(pagePaths().slice(-2)).toEqual(["/v1/pages/page-1/text", "/v1/pages/page-1/leave"]);
  });

  it("a 70 KB page is saved without keepalive when the tab is hidden", async () => {
    await openPage();

    typeInPage("x".repeat(70_000));
    hideTab();

    await waitFor(() => expect(leaves()).toHaveLength(1));
    expect(textPuts()).toHaveLength(1);
    expect(textPuts()[0]!.keepalive).toBe(false);
  });

  it("text typed during a save is sent once it lands, before leaving", async () => {
    const release = holdSaves();
    const { unmount } = await openPage();

    typeInPage("Boleto");
    await act(() => vi.advanceTimersByTimeAsync(1100));
    await waitFor(() => expect(textPuts()).toHaveLength(1));
    typeInPage("no portal");
    unmount();
    await act(() => vi.advanceTimersByTimeAsync(100));
    expect(leaves()).toHaveLength(0);

    await release();
    await release();

    await waitFor(() => expect(leaves()).toHaveLength(1));
    expect(textPuts().map((put) => put.body)).toEqual([
      { markdown: "## Documentos\n\nBoleto\n", revision: 4 },
      { markdown: "## Documentos\n\nBoleto\n\nno portal\n", revision: 5 },
    ]);
    expect(pagePaths()).toEqual(["/v1/pages/page-1/text", "/v1/pages/page-1/text", "/v1/pages/page-1/leave"]);
  });

  it("a stale_page sends what was typed during the refused save before reloading", async () => {
    const release = holdSaves(() => ({
      status: 409,
      body: {
        error: "stale_page",
        message: "page page-1 changed since revision 4",
        details: { markdown: "## Documentos\n\n- Boleto no portal\n", revision: 7 },
      },
    }));
    await openPage();

    typeInPage("Segunda via");
    await act(() => vi.advanceTimersByTimeAsync(1100));
    await waitFor(() => expect(textPuts()).toHaveLength(1));
    typeInPage("Apólice");
    await release();
    await release();

    expect(await screen.findByRole("status")).toHaveTextContent("Esta página mudou em outra aba");
    expect(textPuts().map((put) => put.body)).toEqual([
      { markdown: "## Documentos\n\nSegunda via\n", revision: 4 },
      { markdown: "## Documentos\n\nSegunda via\n\nApólice\n", revision: 4 },
    ]);
    expect(screen.getByText("Boleto no portal")).toBeInTheDocument();
  });

  it("a newer revision from the API reloads an idle editor", async () => {
    const { queryClient } = await openPage();

    respond("GET", "/v1/nodes/page-1", {
      body: pageNode({ markdown: "## Documentos\n\nVer [[Renovação 2026]].\n", revision: 9 }),
    });
    await act(() => queryClient.invalidateQueries({ queryKey: ["node", "page-1"] }));

    expect(await screen.findByText("Renovação 2026")).toBeInTheDocument();
    typeInPage("Boleto");
    await act(() => vi.advanceTimersByTimeAsync(1100));
    await waitFor(() => expect(textPuts().at(-1)?.body).toMatchObject({ revision: 9 }));
  });

  it("a rename made elsewhere is shown and never sent back", async () => {
    const { queryClient } = await openPage();

    respond("GET", "/v1/nodes/page-1", { body: { ...pageNode(), title: "Apólice residencial" } });
    await act(() => queryClient.invalidateQueries({ queryKey: ["node", "page-1"] }));

    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: "Título da página" })).toHaveValue("Apólice residencial"),
    );
    await act(() => vi.advanceTimersByTimeAsync(1100));
    expect(calls.filter((call) => call.method === "PATCH")).toHaveLength(0);
  });

  it("files dropped on the page upload into it", async () => {
    const sent: Array<{ path: string; form: FormData }> = [];
    vi.stubGlobal(
      "XMLHttpRequest",
      class {
        upload = {};
        path = "";
        open(_method: string, path: string) {
          this.path = path;
        }
        setRequestHeader() {}
        send(form: FormData) {
          sent.push({ path: this.path, form });
        }
      },
    );
    await openPage();

    const file = new File(["%PDF"], "Apólice.pdf", { type: "application/pdf" });
    fireEvent.drop(screen.getByRole("textbox", { name: "Texto da página" }), {
      dataTransfer: { files: [file], types: ["Files"] },
    });

    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]!.path).toBe("/v1/kbs/kb-1/files");
    expect(sent[0]!.form.get("parent_id")).toBe("page-1");
    expect(sent[0]!.form.get("file")).toBeInstanceOf(File);
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
