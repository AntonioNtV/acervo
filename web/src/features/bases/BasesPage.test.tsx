import "@testing-library/jest-dom/vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BasesPage } from "./BasesPage";
import { fakeBasesApi, renderPage, summary } from "./fakeApi";

let fake: ReturnType<typeof fakeBasesApi>;

beforeEach(() => {
  localStorage.clear();
  fake = fakeBasesApi([
    summary({ id: "kb-1", name: "Seguros · Operação", description: "Regras de emissão.", pages: 142, files: 38 }),
    summary({ id: "kb-2", name: "Pessoal", pages: 1, files: 1 }),
  ]);
});

afterEach(() => fake.stop());

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
});
