import "@testing-library/jest-dom/vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calls, resetApi, respond } from "../../api/testing";
import { fakeBases, summary } from "../bases/testing";
import { pageNode, renderPage } from "./testing";

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
