import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { I18nProvider } from "../i18n";
import { DatabaseHeader } from "./DatabaseHeader";

const VIEWS = [
  { value: "table", label: "Tabela" },
  { value: "board", label: "Quadro" },
  { value: "gallery", label: "Galeria" },
];

function renderHeader() {
  const onView = vi.fn();
  const tools = { onFilter: vi.fn(), onSort: vi.fn(), onSearch: vi.fn(), onNew: vi.fn() };
  function Controlled() {
    const [view, setView] = useState("table");
    return (
      <DatabaseHeader
        title="Apólices"
        views={VIEWS}
        view={view}
        onView={(next) => {
          onView(next);
          setView(next);
        }}
        {...tools}
      />
    );
  }
  render(
    <I18nProvider>
      <Controlled />
    </I18nProvider>,
  );
  return { onView, ...tools };
}

beforeEach(() => localStorage.clear());

describe("DatabaseHeader", () => {
  it("moves through the views by arrows and by click", async () => {
    const { onView } = renderHeader();
    expect(screen.getByRole("tab", { name: "Tabela" })).toHaveAttribute("aria-selected", "true");

    screen.getByRole("tab", { name: "Tabela" }).focus();
    await userEvent.keyboard("{ArrowLeft}");
    expect(screen.getByRole("tab", { name: "Galeria" })).toHaveFocus();
    expect(screen.getByRole("tab", { name: "Galeria" })).toHaveAttribute("aria-selected", "true");

    await userEvent.keyboard("{ArrowRight}");
    await userEvent.click(screen.getByRole("tab", { name: "Quadro" }));

    expect(onView.mock.calls).toEqual([["gallery"], ["table"], ["board"]]);
  });

  it("reports each tool", async () => {
    const { onFilter, onSort, onSearch, onNew } = renderHeader();

    await userEvent.click(screen.getByRole("button", { name: "Filtrar" }));
    await userEvent.click(screen.getByRole("button", { name: "Ordenar" }));
    await userEvent.click(screen.getByRole("button", { name: "Buscar" }));
    await userEvent.click(screen.getByRole("button", { name: "Nova" }));

    for (const tool of [onFilter, onSort, onSearch, onNew]) expect(tool).toHaveBeenCalledOnce();
  });
});
