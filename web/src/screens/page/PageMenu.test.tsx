import "@testing-library/jest-dom/vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, resetApi, respond } from "../../api/testing";
import { fakeBases, summary } from "../bases/testing";
import { signedIn } from "../settings/testing";
import { pageNode, renderPage, typeInPage } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

beforeEach(() => {
  localStorage.clear();
  resetApi();
  respond("GET", "/v1/nodes/page-1", { body: pageNode() });
  respond("POST", "/v1/pages/page-1/leave", { status: 204, body: "" });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function choose(item: string) {
  await userEvent.click(await screen.findByRole("button", { name: "Mais opções da página" }));
  await userEvent.click(await screen.findByRole("menuitem", { name: item }));
}

describe("PageMenu", () => {
  it("adds the page to the favorites, and takes it out when it is there", async () => {
    let favorite = false;
    const read = () => ({ body: { ...pageNode(), favorite } });
    respond("GET", "/v1/nodes/page-1", read);
    respond("PUT", "/v1/nodes/page-1/favorite", () => ((favorite = true), read()));
    respond("DELETE", "/v1/nodes/page-1/favorite", () => ((favorite = false), read()));
    renderPage();

    await choose("Adicionar aos favoritos");
    await waitFor(() =>
      expect(calls.find((call) => call.method === "PUT")).toMatchObject({
        path: "/v1/nodes/page-1/favorite",
        body: { before_id: null },
      }),
    );

    await choose("Remover dos favoritos");
    await waitFor(() =>
      expect(calls.some((call) => call.method === "DELETE" && call.path === "/v1/nodes/page-1/favorite")).toBe(true),
    );
  });

  it("follows the page and says a digest comes once a day, and unfollows it", async () => {
    signedIn({ preferences: { ...signedIn().preferences, notify_followed: true } });
    let following = false;
    const read = () => ({ body: pageNode({ following }) });
    respond("GET", "/v1/nodes/page-1", read);
    respond("PUT", "/v1/pages/page-1/follow", () => ((following = true), { status: 204, body: undefined }));
    respond("DELETE", "/v1/pages/page-1/follow", () => ((following = false), { status: 204, body: undefined }));
    renderPage();

    await choose("Seguir");
    expect(await screen.findByRole("status")).toHaveTextContent("Seguindo. Um resumo por dia, se ela mudar.");

    await choose("Deixar de seguir");
    await waitFor(() =>
      expect(calls.some((call) => call.method === "DELETE" && call.path === "/v1/pages/page-1/follow")).toBe(true),
    );
    await userEvent.click(await screen.findByRole("button", { name: "Mais opções da página" }));
    expect(await screen.findByRole("menuitem", { name: "Seguir" })).toBeInTheDocument();
  });

  it("following with the digest off points to Notificações", async () => {
    signedIn();
    respond("PUT", "/v1/pages/page-1/follow", { status: 204, body: undefined });
    renderPage();

    await choose("Seguir");

    const notice = await screen.findByRole("status");
    expect(notice).toHaveTextContent("Seguindo. O resumo diário está desligado em Notificações.");
    expect(within(notice).getByRole("link", { name: "Notificações" })).toHaveAttribute("href", "/conta/notificacoes");
  });

  it("duplicating opens the copy", async () => {
    const copy = { ...pageNode(), id: "copy-1", title: "Emissão de apólice (cópia)" };
    respond("POST", "/v1/nodes/page-1/duplicate", { status: 201, body: copy });
    respond("GET", "/v1/nodes/copy-1", { body: copy });
    renderPage();

    await choose("Duplicar");

    expect(await screen.findByDisplayValue("Emissão de apólice (cópia)")).toBeInTheDocument();
  });

  it("moving to another base sends its id and names the files it already holds", async () => {
    fakeBases([summary({ id: "kb-1", name: "Seguros · Operação" }), summary({ id: "kb-2", name: "Pessoal" })]);
    respond("POST", "/v1/nodes/page-1/move", {
      status: 409,
      body: { error: "conflict", message: "já está na base de destino", details: { files: ["CG 2026.pdf"] } },
    });
    renderPage();

    await choose("Mover para…");
    const picker = await screen.findByRole("dialog", { name: "Mover Emissão de apólice para" });
    await userEvent.click(await within(picker).findByRole("button", { name: "Pessoal" }));

    expect(await within(picker).findByRole("alert")).toHaveTextContent("Já está na base de destino: CG 2026.pdf.");
    expect(calls.find((call) => call.method === "POST" && call.path === "/v1/nodes/page-1/move")?.body).toEqual({
      kb_id: "kb-2",
      parent_id: null,
      before_id: null,
    });
  });

  it("moving sends the text still being typed first", async () => {
    fakeBases([summary({ id: "kb-1", name: "Seguros · Operação" }), summary({ id: "kb-2", name: "Pessoal" })]);
    respond("PUT", "/v1/pages/page-1/text", { body: { revision: 5, saved_at: "2026-10-22T10:00:00Z" } });
    respond("POST", "/v1/nodes/page-1/move", { body: { ...pageNode(), kb_id: "kb-2" } });
    renderPage();
    await screen.findByRole("textbox", { name: "Texto da página" });

    typeInPage("Prazo de 5 dias.");
    await choose("Mover para…");
    const picker = await screen.findByRole("dialog", { name: "Mover Emissão de apólice para" });
    await userEvent.click(await within(picker).findByRole("button", { name: "Pessoal" }));

    await waitFor(() => expect(calls.some((call) => call.path === "/v1/nodes/page-1/move")).toBe(true));
    const save = calls.findIndex((call) => call.method === "PUT" && call.path === "/v1/pages/page-1/text");
    expect(save).toBeGreaterThan(-1);
    expect(save).toBeLessThan(calls.findIndex((call) => call.path === "/v1/nodes/page-1/move"));
    expect((calls[save]!.body as { markdown: string }).markdown).toContain("Prazo de 5 dias.");
  });

  it("copying the link writes the page's address", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    // jsdom has no clipboard.
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    renderPage();

    await choose("Copiar link");

    expect(await screen.findByRole("status")).toHaveTextContent("Link copiado");
    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/kbs/kb-1/n/page-1`);
  });

  it("exporting asks for the link and goes to it", async () => {
    respond("POST", "/v1/nodes/page-1/export/link", {
      body: { url: "http://api.test/v1/nodes/page-1/export?expires=1&signature=s", expires_at: "2026-10-22T10:01:00Z" },
    });
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    renderPage();

    await choose("Exportar");

    await waitFor(() => expect(assign).toHaveBeenCalledWith("/v1/nodes/page-1/export?expires=1&signature=s"));
  });
});
