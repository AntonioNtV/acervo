import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nProvider } from "../i18n";
import { PersonPicker, type Person } from "./PersonPicker";

const PEOPLE: Person[] = [
  { id: "1", name: "Ana Souza", email: "ana.souza@segura.com.br" },
  { id: "2", name: "André Lima", email: "andre.lima@segura.com.br" },
];

function renderPicker(people: Person[]) {
  const onPick = vi.fn();
  const onClose = vi.fn();
  render(
    <I18nProvider>
      <PersonPicker query="an" people={people} onPick={onPick} onClose={onClose} />
    </I18nProvider>,
  );
  return { onPick, onClose };
}

beforeEach(() => localStorage.clear());

describe("PersonPicker", () => {
  it("lists the people with initials and picks by arrows and Enter", async () => {
    const { onPick } = renderPicker(PEOPLE);
    expect(screen.getByRole("listbox", { name: "Pessoas para “an”" })).toBeInTheDocument();
    expect(screen.getByText("AS")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Ana Souza/ })).toHaveAttribute("aria-selected", "true");

    await userEvent.keyboard("{ArrowDown}");
    expect(screen.getByRole("option", { name: /André Lima/ })).toHaveAttribute("aria-selected", "true");

    await userEvent.keyboard("{Enter}");
    expect(onPick).toHaveBeenCalledWith(PEOPLE[1]);
  });

  it("says when no one matches and closes on Escape", async () => {
    const { onPick, onClose } = renderPicker([]);
    expect(screen.getByText("Ninguém com esse nome")).toBeInTheDocument();

    await userEvent.keyboard("{Enter}{Escape}");
    expect(onPick).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalledOnce();
  });
});
