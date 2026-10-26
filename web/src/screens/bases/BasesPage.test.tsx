import "@testing-library/jest-dom/vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BasesPage } from "./BasesPage";
import { resetApi } from "../../api/testing";
import { fakeBases, renderPage, summary } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

beforeEach(() => {
  localStorage.clear();
  resetApi();
  fakeBases([
    summary({
      id: "kb-1",
      name: "Seguros · Operação",
      description: "Regras de emissão.",
      pages: 142,
      files: 38,
      my_role: "admin",
    }),
    summary({ id: "kb-2", name: "Pessoal", pages: 1, files: 1, my_role: "admin" }),
  ]);
});

describe("BasesPage", () => {
  it("lists bases with counts", async () => {
    renderPage(<BasesPage />);

    const seguros = (await screen.findByRole("link", { name: "Seguros · Operação" })).closest("article")!;
    expect(seguros).toHaveTextContent("Regras de emissão.");
    expect(seguros).toHaveTextContent("142 páginas · 38 arquivos");
    const pessoal = screen.getByRole("link", { name: "Pessoal" }).closest("article")!;
    expect(pessoal).toHaveTextContent("1 página · 1 arquivo");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Bases 2");
  });

  it("shows the bases shared with the person under Compartilhadas comigo, with the owner's name", async () => {
    fakeBases([
      summary({ id: "kb-1", name: "Receitas" }),
      summary({ id: "kb-2", name: "Viagens", organization_id: "org-julia", shared_by: "Julia Prado" }),
    ]);
    renderPage(<BasesPage />);

    const shared = await screen.findByRole("region", { name: "Compartilhadas comigo" });
    const viagens = within(shared).getByRole("link", { name: "Viagens" }).closest("article")!;
    expect(viagens).toHaveTextContent("De Julia Prado");
    expect(within(shared).queryByRole("link", { name: "Receitas" })).not.toBeInTheDocument();
  });

  it("creating adds a card", async () => {
    renderPage(<BasesPage />);
    await screen.findByRole("link", { name: "Pessoal" });

    await userEvent.click(screen.getAllByRole("button", { name: "Nova base" })[0]!);
    const dialog = screen.getByRole("dialog", { name: "Nova base" });
    await userEvent.type(within(dialog).getByLabelText("Nome"), "Engenharia · Runbooks");
    await userEvent.type(within(dialog).getByLabelText("Descrição"), "Deploy e plantão.");
    await userEvent.click(within(dialog).getByRole("button", { name: "Criar" }));

    const created = (await screen.findByRole("link", { name: "Engenharia · Runbooks" })).closest("article")!;
    expect(created).toHaveTextContent("Deploy e plantão.");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("trashing removes it", async () => {
    renderPage(<BasesPage />);
    await screen.findByRole("link", { name: "Pessoal" });

    await userEvent.click(screen.getByRole("button", { name: "Ações de Pessoal" }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "Mover para a Lixeira" }));

    await screen.findByRole("heading", { name: "Bases 1" });
    expect(screen.queryByRole("link", { name: "Pessoal" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Seguros · Operação" })).toBeInTheDocument();
  });

  it("offers the card's actions only to the base's Admin, also under Compartilhadas comigo", async () => {
    fakeBases([
      summary({ id: "kb-1", name: "Receitas", my_role: "editor" }),
      summary({ id: "kb-2", name: "Viagens", organization_id: "org-julia", shared_by: "Julia Prado", my_role: "reader" }),
      summary({ id: "kb-3", name: "Roteiros", organization_id: "org-julia", shared_by: "Julia Prado", my_role: "admin" }),
    ]);
    renderPage(<BasesPage />);
    await screen.findByRole("link", { name: "Receitas" });

    expect(screen.queryByRole("button", { name: "Ações de Receitas" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ações de Viagens" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Ações de Roteiros" }));
    expect(await screen.findByRole("menuitem", { name: "Renomear" })).toBeInTheDocument();
  });
});
