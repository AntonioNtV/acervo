import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { calls, node, resetApi, respond } from "../../api/testing";
import { Providers } from "../../app/Providers";
import { ShellFrame } from "../../app/ShellFrame";
import { fakeBases, summary } from "../bases/testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

const titles = [
  { ...node("bradesco", "folder", "Bradesco"), path: "Bradesco" },
  { ...node("emissao", "page", "Emissão de apólice", "bradesco"), path: "Bradesco/Emissão de apólice" },
  { ...node("cg", "file", "CG 2026.pdf", "bradesco"), path: "Bradesco/CG 2026.pdf" },
];

const plain = (text: string) => text.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();

beforeEach(() => {
  localStorage.clear();
  resetApi();
  fakeBases([summary({ id: "kb-1", name: "Seguros · Operação" })]);
  respond("GET", "/v1/kbs/kb-1/children", { body: [] });
  respond("GET", "/v1/kbs/kb-1/search", (url) => {
    const q = plain(url.searchParams.get("q") ?? "");
    return { body: titles.filter((hit) => plain(hit.title).includes(q)) };
  });
  respond("GET", "/v1/nodes/renovacao", { body: { ...node("renovacao", "page", "Renovação"), path: "Renovação" } });
  respond("GET", "/v1/nodes/glossario", { body: { ...node("glossario", "page", "Glossário"), path: "Glossário" } });
});

function renderShell(path = "/kbs/kb-1/n/glossario") {
  const router = createMemoryRouter(
    [{ element: <ShellFrame />, children: [{ path: "/kbs/:kbId/n/:nodeId", element: null }] }],
    { initialEntries: [path] },
  );
  render(
    <Providers>
      <RouterProvider router={router} />
    </Providers>,
  );
  return router;
}

async function openWithShortcut() {
  await userEvent.keyboard("{Meta>}k{/Meta}");
  return screen.findByRole("dialog", { name: "Buscar" });
}

describe("SearchPalette", () => {
  it("opens on ⌘K and Esc closes it", async () => {
    renderShell();

    const dialog = await openWithShortcut();
    expect(within(dialog).getByRole("combobox", { name: "Buscar" })).toHaveFocus();
    expect(dialog).toHaveTextContent("em Seguros · Operação");

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "Buscar" })).not.toBeInTheDocument();
  });

  it("opens from the sidebar", async () => {
    renderShell();

    await userEvent.click(screen.getByRole("button", { name: /^Buscar/ }));

    expect(await screen.findByRole("dialog", { name: "Buscar" })).toBeInTheDocument();
  });

  it("empty, it shows the base's recent pages as they are now", async () => {
    respond("GET", "/v1/nodes/apagada", { status: 404, body: { error: "not_found", message: "gone" } });
    localStorage.setItem("acervo.recent.kb-1", JSON.stringify(["renovacao", "apagada", "glossario"]));
    renderShell();

    const dialog = await openWithShortcut();

    expect(within(dialog).getByText("Recentes")).toBeInTheDocument();
    await waitFor(() =>
      expect(within(dialog).getAllByRole("option").map((option) => option.textContent)).toEqual(["Renovação", "Glossário"]),
    );
  });

  it("typing lists the results and Enter opens the selected one", async () => {
    const router = renderShell();
    await openWithShortcut();

    await userEvent.keyboard("emis");

    const hit = await screen.findByRole("option", { name: /Emissão de apólice/ });
    expect(hit).toHaveTextContent("Bradesco");
    expect(hit).toHaveAttribute("aria-selected", "true");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => expect(router.state.location.pathname).toBe("/kbs/kb-1/n/emissao"));
    expect(screen.queryByRole("dialog", { name: "Buscar" })).not.toBeInTheDocument();
  });

  it("arrows move the selection, and the last item creates a page", async () => {
    await renderAndType("d");
    const [bradesco, emissao, , createRow] = await waitFor(() => {
      const options = screen.getAllByRole("option");
      expect(options).toHaveLength(4);
      return options;
    });
    expect(bradesco).toHaveAttribute("aria-selected", "true");

    await userEvent.keyboard("{ArrowDown}");
    expect(emissao).toHaveAttribute("aria-selected", "true");
    expect(bradesco).toHaveAttribute("aria-selected", "false");

    await userEvent.keyboard("{ArrowDown}{ArrowDown}{ArrowDown}");
    expect(createRow).toHaveAttribute("aria-selected", "true");
    expect(createRow).toHaveTextContent("Criar página “d”");

    await userEvent.keyboard("{ArrowUp}{ArrowUp}");
    expect(emissao).toHaveAttribute("aria-selected", "true");
  });

  it("“Criar página” creates the page at the root and opens it", async () => {
    respond("POST", "/v1/kbs/kb-1/nodes", { status: 201, body: node("novo", "page", "Novo") });
    const router = await renderAndType("Novo");

    await userEvent.click(await screen.findByRole("option", { name: "Criar página “Novo”" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/kbs/kb-1/n/novo"));
    expect(calls.find((call) => call.method === "POST")).toMatchObject({
      path: "/v1/kbs/kb-1/nodes",
      body: { kind: "page", parent_id: null, title: "Novo" },
    });
    expect(screen.queryByRole("dialog", { name: "Buscar" })).not.toBeInTheDocument();
  });
});

async function renderAndType(text: string) {
  const router = renderShell();
  await openWithShortcut();
  await userEvent.keyboard(text);
  return router;
}
