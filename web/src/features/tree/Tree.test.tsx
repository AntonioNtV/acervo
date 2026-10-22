import "@testing-library/jest-dom/vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BaseLayout } from "./BaseLayout";
import { calls, node, renderInBase, resetApi, respond } from "./testing";

vi.mock("../../api/client", () => import("./testing").then((m) => m.mockClient()));

beforeEach(() => {
  localStorage.clear();
  resetApi();
  respond("GET", "/kbs", { body: [] });
  respond("GET", "/kbs/kb-1/children", (url) => {
    const parent = url.searchParams.get("parent_id");
    if (parent === "bradesco") {
      return {
        body: [
          node("residencial", "folder", "Residencial", "bradesco"),
          { ...node("cg", "file", "Condições Gerais 2026.pdf", "bradesco"), protected: true },
          node("emissao", "page", "Emissão de apólice", "bradesco"),
        ],
      };
    }
    return { body: [node("bradesco", "folder", "Bradesco"), node("glossario", "page", "Glossário")] };
  });
});

async function openRename(name: string) {
  await userEvent.click(await screen.findByRole("button", { name: `Ações de ${name}` }));
  await userEvent.click(await screen.findByRole("menuitem", { name: "Renomear" }));
  return screen.findByRole("textbox", { name: "Renomear" });
}

describe("Tree", () => {
  it("expands a folder and lists its children in order", async () => {
    renderInBase(<BaseLayout />);

    await userEvent.click(await screen.findByRole("button", { name: "Expandir Bradesco" }));

    const bradesco = screen.getByRole("treeitem", { name: "Bradesco" });
    expect(bradesco).toHaveAttribute("aria-expanded", "true");
    const group = await within(bradesco).findByRole("group");
    await within(group).findByText("Residencial");
    const children = within(group).getAllByRole("treeitem");
    expect(children.map((item) => item.textContent)).toEqual([
      "Residencial",
      "Condições Gerais 2026.pdfprotegido",
      "Emissão de apólice.md",
    ]);
    expect(screen.getAllByRole("treeitem").at(-1)).toHaveTextContent("Glossário.md");
  });

  it("renames an item inline", async () => {
    respond("PATCH", "/nodes/glossario", { body: node("glossario", "page", "Termos") });
    renderInBase(<BaseLayout />);

    const input = await openRename("Glossário");
    expect(input).toHaveValue("Glossário");
    await userEvent.clear(input);
    await userEvent.type(input, "Termos{Enter}");

    await waitFor(() =>
      expect(calls.find((call) => call.method === "PATCH")).toMatchObject({
        path: "/nodes/glossario",
        body: { title: "Termos" },
      }),
    );
    await waitFor(() => expect(screen.queryByRole("textbox", { name: "Renomear" })).not.toBeInTheDocument());
  });

  it("says a taken name already exists and keeps the input", async () => {
    respond("PATCH", "/nodes/glossario", {
      status: 409,
      body: { error: "ConflictError", message: "já existe", detail: { title: "Bradesco" } },
    });
    renderInBase(<BaseLayout />);

    const input = await openRename("Glossário");
    await userEvent.clear(input);
    await userEvent.type(input, "Bradesco{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent("já existe");
    expect(screen.getByRole("textbox", { name: "Renomear" })).toHaveValue("Bradesco");
  });
});
