import "@testing-library/jest-dom/vitest";
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, resetApi, respond } from "../../api/testing";
import { summary } from "../bases/testing";
import { pageNode, renderPage, typeInPage } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

const textPuts = () => calls.filter((call) => call.method === "PUT" && call.path === "/v1/pages/page-1/text");
const leaves = () => calls.filter((call) => call.path === "/v1/pages/page-1/leave");
const nodePatches = () => calls.filter((call) => call.method === "PATCH" && call.path === "/v1/nodes/page-1");
const pagePaths = () =>
  calls.filter((call) => call.method !== "GET" && call.path.startsWith("/v1/pages/")).map((call) => call.path);

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

  it("text typed during the stale_page resend is sent as well", async () => {
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
    await waitFor(() => expect(textPuts()).toHaveLength(2));
    typeInPage("Boleto");
    await release();
    await release();

    expect(await screen.findByRole("status")).toHaveTextContent("Esta página mudou em outra aba");
    expect(textPuts().map((put) => (put.body as { markdown: string }).markdown)).toEqual([
      "## Documentos\n\nSegunda via\n",
      "## Documentos\n\nSegunda via\n\nApólice\n",
      "## Documentos\n\nSegunda via\n\nApólice\n\nBoleto\n",
    ]);
  });

  it("hiding the tab during a save sends the rest and leaves at once", async () => {
    holdSaves();
    await openPage();

    typeInPage("Boleto");
    await act(() => vi.advanceTimersByTimeAsync(1100));
    await waitFor(() => expect(textPuts()).toHaveLength(1));
    typeInPage("no portal");
    hideTab();

    // The first save never answers: a closing tab would not wait for it.
    await waitFor(() => expect(leaves()).toHaveLength(1));
    expect(textPuts().map((put) => put.keepalive)).toEqual([false, true]);
    expect(textPuts()[1]!.body).toEqual({ markdown: "## Documentos\n\nBoleto\n\nno portal\n", revision: 4 });
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

  it("files dropped on the page outside its text upload into it", async () => {
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
    fireEvent.drop(screen.getByRole("textbox", { name: "Título da página" }), {
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

  it("an emoji picked in the header is sent as the node's icon", async () => {
    respond("PATCH", "/v1/nodes/page-1", { body: { ...pageNode(), icon: "🏠" } });
    await openPage();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    await user.click(screen.getByRole("button", { name: "Adicionar ícone" }));
    const picker = screen.getByRole("dialog", { name: "Escolher ícone" });
    await user.type(within(picker).getByRole("searchbox", { name: "Buscar emoji" }), "casa");
    await user.click(within(picker).getByRole("button", { name: "casa" }));

    await waitFor(() => expect(nodePatches().map((call) => call.body)).toEqual([{ icon: "🏠" }]));
  });

  it("a cover from the gallery is sent as the node's cover", async () => {
    respond("PATCH", "/v1/nodes/page-1", { body: { ...pageNode(), cover: "gallery:sand" } });
    await openPage();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    await user.click(screen.getByRole("button", { name: "Adicionar capa" }));
    await user.click(await screen.findByRole("menuitem", { name: "Areia" }));

    await waitFor(() => expect(nodePatches().map((call) => call.body)).toEqual([{ cover: "gallery:sand" }]));
  });

  it("an uploaded image goes to the cover route and shows through its signed link", async () => {
    const sent: Array<{ path: string; form: FormData }> = [];
    vi.stubGlobal(
      "XMLHttpRequest",
      class {
        upload = {};
        path = "";
        status = 0;
        response: unknown = null;
        onload = () => {};
        open(_method: string, path: string) {
          this.path = path;
        }
        setRequestHeader() {}
        send(form: FormData) {
          sent.push({ path: this.path, form });
          respond("GET", "/v1/nodes/page-1", { body: { ...pageNode(), cover: "image:abc" } });
          this.status = 200;
          this.response = { ...pageNode(), cover: "image:abc" };
          this.onload();
        }
      },
    );
    respond("POST", "/v1/nodes/page-1/cover/link", {
      body: {
        url: "http://api.test/v1/nodes/page-1/cover/raw?expires=1&signature=s",
        expires_at: new Date(Date.now() + 60_000).toISOString(),
      },
    });
    await openPage();

    const image = new File(["\x89PNG"], "capa.png", { type: "image/png" });
    await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).upload(screen.getByLabelText("Enviar imagem"), image);

    expect(sent.map((request) => request.path)).toEqual(["/v1/nodes/page-1/cover"]);
    expect(sent[0]!.form.get("file")).toBeInstanceOf(File);
    expect(await screen.findByRole("img", { name: "Capa" })).toHaveAttribute(
      "src",
      "/v1/nodes/page-1/cover/raw?expires=1&signature=s",
    );
  });

  it("Remover clears the cover and the icon", async () => {
    respond("GET", "/v1/nodes/page-1", { body: { ...pageNode(), icon: "🏠", cover: "gallery:sky" } });
    respond("PATCH", "/v1/nodes/page-1", { body: pageNode() });
    await openPage();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    await user.click(screen.getByRole("button", { name: "Remover" }));
    await user.click(screen.getByRole("button", { name: "Trocar ícone" }));
    await user.click(within(screen.getByRole("dialog", { name: "Escolher ícone" })).getByRole("button", { name: "Remover" }));

    await waitFor(() => expect(nodePatches().map((call) => call.body)).toEqual([{ cover: null }, { icon: null }]));
  });

  it("as Leitor the page is read-only and its menu changes nothing", async () => {
    respond("GET", "/v1/kbs", { body: [summary({ id: "kb-1", name: "Bradesco", my_role: "reader" })] });
    renderPage();

    const text = await screen.findByRole("textbox", { name: "Texto da página" });
    await waitFor(() => expect(text).toHaveAttribute("contenteditable", "false"));
    expect(screen.getByRole("textbox", { name: "Título da página" })).toHaveAttribute("readonly");
    await userEvent.click(screen.getByRole("button", { name: "Mais opções da página" }));
    expect(await screen.findByRole("menuitem", { name: "Copiar link" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Mover para…" })).not.toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Mover para a Lixeira" })).not.toBeInTheDocument();
  });
});
