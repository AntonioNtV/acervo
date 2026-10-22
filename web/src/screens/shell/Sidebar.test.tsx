import "@testing-library/jest-dom/vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { calls, node, renderWithApi, resetApi, respond } from "../../api/testing";
import { ThemeProvider } from "../../app/theme";
import { fakeBases, summary } from "../bases/testing";
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
        node("renovacao", "page", "Renovação"),
        node("glossario", "page", "Glossário"),
      ],
    };
  });
});

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
});
