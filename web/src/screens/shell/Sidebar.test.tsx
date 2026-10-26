import "@testing-library/jest-dom/vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { calls, node, renderWithApi, resetApi, respond } from "../../api/testing";
import { ThemeProvider } from "../../app/theme";
import { fakeBases, summary } from "../bases/testing";
import { signedIn } from "../settings/testing";
import { Sidebar } from "./Sidebar";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

beforeEach(() => {
  localStorage.clear();
  resetApi();
  fakeBases([summary({ id: "kb-1", name: "Seguros · Operação" }), summary({ id: "kb-2", name: "Pessoal" })]);
  respond("GET", "/v1/kbs/kb-1/children", (url) => {
    const parent = url.searchParams.get("parent_id");
    if (parent === "bradesco") return { body: [node("residencial", "folder", "Residencial", "bradesco")] };
    if (parent === "renovacao") return { body: [node("documentos", "page", "Documentos exigidos", "renovacao")] };
    if (parent) return { body: [] };
    return {
      body: [
        node("bradesco", "folder", "Bradesco"),
        { ...node("renovacao", "page", "Renovação"), child_count: 1 },
        node("glossario", "page", "Glossário"),
      ],
    };
  });
});

function organization(id: string, name: string, personal = false) {
  return { id, name, personal, logo_url: null, my_role: "owner", new_base_access: "editor" };
}

function favorite(id: string, title: string, kbId: string) {
  return { ...node(id, "page", title), kb_id: kbId, path: title };
}

function renderSidebar() {
  return renderWithApi(
    <ThemeProvider>
      <MemoryRouter initialEntries={["/kbs/kb-1"]}>
        <Sidebar />
      </MemoryRouter>
    </ThemeProvider>,
  );
}

async function openRename(name: string) {
  await userEvent.click(await screen.findByRole("button", { name: `Ações de ${name}` }));
  await userEvent.click(await screen.findByRole("menuitem", { name: "Renomear" }));
  return screen.findByRole("textbox", { name: "Renomear" });
}

describe("Sidebar", () => {
  it("lists every base", async () => {
    renderSidebar();

    expect(await screen.findByRole("region", { name: "Seguros · Operação" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Pessoal" })).toBeInTheDocument();
  });

  it("expanding a folder loads its children", async () => {
    renderSidebar();

    await userEvent.click(await screen.findByRole("button", { name: "Expandir Bradesco" }));

    const bradesco = screen.getByRole("treeitem", { name: "Bradesco" });
    expect(bradesco).toHaveAttribute("aria-expanded", "true");
    expect(await within(bradesco).findByRole("treeitem", { name: "Residencial" })).toBeInTheDocument();
    expect(calls.some((call) => call.path === "/v1/kbs/kb-1/children" && call.query === "?parent_id=bradesco")).toBe(true);
  });

  it("a page with children shows a caret", async () => {
    renderSidebar();

    await userEvent.click(await screen.findByRole("button", { name: "Expandir Renovação" }));

    const renovacao = screen.getByRole("treeitem", { name: "Renovação" });
    expect(await within(renovacao).findByRole("treeitem", { name: "Documentos exigidos" })).toBeInTheDocument();
    expect(screen.getByRole("treeitem", { name: "Glossário" })).not.toHaveAttribute("aria-expanded");
    expect(screen.queryByRole("button", { name: "Expandir Glossário" })).not.toBeInTheDocument();
  });

  it("dropping on a page moves into it", async () => {
    respond("POST", "/v1/nodes/glossario/move", { body: node("glossario", "page", "Glossário", "renovacao") });
    renderSidebar();
    const glossario = (await screen.findByRole("treeitem", { name: "Glossário" })).firstElementChild!;
    const renovacao = screen.getByRole("treeitem", { name: "Renovação" }).firstElementChild!;
    const data = new Map<string, string>();
    const dataTransfer = {
      files: [],
      types: [] as string[],
      setData: (type: string, value: string) => data.set(type, value),
      getData: (type: string) => data.get(type) ?? "",
    };

    fireEvent.dragStart(glossario, { dataTransfer });
    fireEvent.drop(renovacao, { dataTransfer });

    await waitFor(() =>
      expect(calls.find((call) => call.method === "POST")).toMatchObject({
        path: "/v1/nodes/glossario/move",
        body: { parent_id: "renovacao", before_id: null },
      }),
    );
  });

  it("renames an item inline", async () => {
    respond("PATCH", "/v1/nodes/glossario", { body: node("glossario", "page", "Termos") });
    renderSidebar();

    const input = await openRename("Glossário");
    expect(input).toHaveValue("Glossário");
    await userEvent.clear(input);
    await userEvent.type(input, "Termos{Enter}");

    await waitFor(() =>
      expect(calls.find((call) => call.method === "PATCH")).toMatchObject({
        path: "/v1/nodes/glossario",
        body: { title: "Termos" },
      }),
    );
    await waitFor(() => expect(screen.queryByRole("textbox", { name: "Renomear" })).not.toBeInTheDocument());
  });

  it("says a taken name already exists and keeps the input", async () => {
    respond("PATCH", "/v1/nodes/glossario", {
      status: 409,
      body: { error: "title_taken", message: "já existe", details: { title: "Bradesco" } },
    });
    renderSidebar();

    const input = await openRename("Glossário");
    await userEvent.clear(input);
    await userEvent.type(input, "Bradesco{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent("já existe");
    expect(screen.getByRole("textbox", { name: "Renomear" })).toHaveValue("Bradesco");
  });

  it("a node's emoji shows in the tree in place of its kind's icon", async () => {
    respond("GET", "/v1/kbs/kb-1/children", () => ({ body: [{ ...node("glossario", "page", "Glossário"), icon: "📒" }] }));
    renderSidebar();

    const glossario = await screen.findByRole("treeitem", { name: "Glossário" });
    expect(within(glossario).getByText("📒")).toBeInTheDocument();
  });

  it("shows the favorites on top, each with its base", async () => {
    respond("GET", "/v1/favorites", { body: [favorite("glossario", "Glossário", "kb-1"), favorite("receitas", "Receitas", "kb-2")] });
    renderSidebar();

    const favorites = await screen.findByRole("region", { name: "Favoritos" });
    const first = await screen.findByRole("region", { name: "Seguros · Operação" });
    expect(favorites.compareDocumentPosition(first) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const receitas = await within(favorites).findByRole("link", { name: /Receitas/ });
    expect(receitas).toHaveAttribute("href", "/kbs/kb-2/n/receitas");
    expect(await within(receitas).findByText("Pessoal")).toBeInTheDocument();
  });

  it("dragging a favorite onto another puts it before that one", async () => {
    respond("GET", "/v1/favorites", { body: [favorite("glossario", "Glossário", "kb-1"), favorite("receitas", "Receitas", "kb-2")] });
    respond("PUT", "/v1/nodes/receitas/favorite", { body: node("receitas", "page", "Receitas") });
    renderSidebar();
    const favorites = await screen.findByRole("region", { name: "Favoritos" });
    const [glossario, receitas] = within(favorites).getAllByRole("listitem");
    const data = new Map<string, string>();
    const dataTransfer = {
      files: [],
      types: [] as string[],
      setData: (type: string, value: string) => data.set(type, value),
      getData: (type: string) => data.get(type) ?? "",
    };

    fireEvent.dragStart(receitas!, { dataTransfer });
    fireEvent.drop(glossario!, { dataTransfer });

    await waitFor(() =>
      expect(calls.find((call) => call.method === "PUT")).toMatchObject({
        path: "/v1/nodes/receitas/favorite",
        body: { before_id: "glossario" },
      }),
    );
  });

  it("hides the favorites when there are none", async () => {
    respond("GET", "/v1/favorites", { body: [] });
    renderSidebar();

    await screen.findByRole("region", { name: "Seguros · Operação" });
    await waitFor(() => expect(calls.some((call) => call.path === "/v1/favorites")).toBe(true));
    expect(screen.queryByRole("region", { name: "Favoritos" })).not.toBeInTheDocument();
  });

  it("lists Pessoal first in the rail and switching organization shows its bases", async () => {
    const organizations = [organization("org-pessoal", "Antonio Bertino", true), organization("org-seguros", "Seguros SA")];
    respond("GET", "/v1/organizations", { body: organizations });
    respond("GET", "/v1/kbs", (url) => ({
      body:
        url.searchParams.get("organization_id") === "org-seguros"
          ? [summary({ id: "kb-3", name: "Sinistros", organization_id: "org-seguros" })]
          : [summary({ id: "kb-2", name: "Receitas" })],
    }));
    renderSidebar();

    const rail = await screen.findByRole("navigation", { name: "Organizações" });
    const [pessoal, seguros] = within(rail).getAllByRole("button");
    expect(pessoal).toHaveAccessibleName("Pessoal");
    expect(pessoal).toHaveAttribute("aria-current", "true");
    expect(await screen.findByRole("region", { name: "Receitas" })).toBeInTheDocument();

    await userEvent.click(seguros!);

    expect(await screen.findByRole("region", { name: "Sinistros" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Receitas" })).not.toBeInTheDocument();
    expect(seguros).toHaveAttribute("aria-current", "true");
    expect(pessoal).not.toHaveAttribute("aria-current");
  });

  it("Nova organização creates one and switches to it", async () => {
    const organizations = [organization("org-pessoal", "Antonio Bertino", true)];
    respond("GET", "/v1/organizations", () => ({ body: organizations }));
    respond("POST", "/v1/organizations", (_url, body) => {
      const created = organization("org-nova", (body as { name: string }).name);
      organizations.push(created);
      return { status: 201, body: created };
    });
    renderSidebar();

    await userEvent.click(await screen.findByRole("button", { name: "Nova organização" }));
    const dialog = screen.getByRole("dialog", { name: "Nova organização" });
    await userEvent.type(within(dialog).getByLabelText("Nome"), "Seguros SA");
    await userEvent.click(within(dialog).getByRole("button", { name: "Criar" }));

    expect(await screen.findByRole("button", { name: "Seguros SA" })).toHaveAttribute("aria-current", "true");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await waitFor(() =>
      expect(calls.some((call) => call.path === "/v1/kbs" && call.query.includes("organization_id=org-nova"))).toBe(true),
    );
  });

  it("Sair ends the session, opens Entrar and drops what the account had loaded", async () => {
    signedIn();
    respond("POST", "/v1/auth/sign-out", { body: {} });
    localStorage.setItem("acervo.lastPage", "/kbs/kb-1/n/glossario");
    const { queryClient } = renderWithApi(
      <ThemeProvider>
        <MemoryRouter initialEntries={["/kbs/kb-1"]}>
          <Routes>
            <Route path="/kbs/:kbId" element={<Sidebar />} />
            <Route path="/entrar" element={<p>Entrar</p>} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>,
    );

    await userEvent.click(await screen.findByRole("button", { name: /Antonio Bertino/ }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "Sair" }));

    expect(await screen.findByText("Entrar")).toBeInTheDocument();
    expect(calls.some((call) => call.method === "POST" && call.path === "/v1/auth/sign-out")).toBe(true);
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0);
    expect(localStorage.getItem("acervo.lastPage")).toBeNull();
  });
});
