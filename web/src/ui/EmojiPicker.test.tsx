import "@testing-library/jest-dom/vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nProvider } from "../i18n";
import { EmojiPicker } from "./EmojiPicker";

function renderPicker(onRemove?: () => void) {
  const onPick = vi.fn();
  const onClose = vi.fn();
  render(
    <I18nProvider>
      <div>
        <EmojiPicker onPick={onPick} onRemove={onRemove} onClose={onClose} />
      </div>
    </I18nProvider>,
  );
  return { onPick, onClose, picker: screen.getByRole("dialog", { name: "Escolher ícone" }) };
}

beforeEach(() => localStorage.clear());

describe("EmojiPicker", () => {
  it("searches by the pt-BR or English name and picks", async () => {
    const { onPick, picker } = renderPicker();
    const search = within(picker).getByRole("searchbox", { name: "Buscar emoji" });

    await userEvent.type(search, "residencia");
    expect(within(picker).getAllByRole("button").map((button) => button.textContent)).toEqual(["🏠"]);

    await userEvent.clear(search);
    await userEvent.type(search, "insurance");
    await userEvent.click(within(picker).getByRole("button", { name: "escudo" }));

    expect(onPick).toHaveBeenCalledWith("🛡️");
    expect(within(picker).queryByRole("button", { name: "Remover" })).not.toBeInTheDocument();
  });

  it("filters by the query it is given, with no search field of its own", () => {
    render(
      <I18nProvider>
        <div>
          <EmojiPicker query="cas" onPick={vi.fn()} onClose={vi.fn()} />
        </div>
      </I18nProvider>,
    );
    const picker = screen.getByRole("dialog", { name: "Escolher ícone" });

    expect(within(picker).getAllByRole("button").map((button) => button.textContent)).toEqual(["🏠"]);
    expect(within(picker).queryByRole("searchbox")).not.toBeInTheDocument();
  });

  it("removes the icon there is", async () => {
    const onRemove = vi.fn();
    const { onPick, picker } = renderPicker(onRemove);

    await userEvent.click(within(picker).getByRole("button", { name: "Remover" }));

    expect(onRemove).toHaveBeenCalledOnce();
    expect(onPick).not.toHaveBeenCalled();
  });
});
