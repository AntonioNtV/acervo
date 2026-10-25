import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nProvider } from "../i18n";
import { ColorMenu, type TextColor } from "./ColorMenu";

function renderMenu(color: TextColor | null, highlight = false) {
  const onColor = vi.fn();
  const onHighlight = vi.fn();
  const onClose = vi.fn();
  render(
    <I18nProvider>
      <ColorMenu color={color} highlight={highlight} onColor={onColor} onHighlight={onHighlight} onClose={onClose} />
    </I18nProvider>,
  );
  return { onColor, onHighlight, onClose };
}

beforeEach(() => localStorage.clear());

describe("ColorMenu", () => {
  it("marks the applied color and picks another by keyboard", async () => {
    const { onColor } = renderMenu("blue");
    const blue = screen.getByRole("menuitemradio", { name: "Azul" });

    expect(blue).toHaveAttribute("aria-checked", "true");
    expect(blue).toHaveFocus();

    await userEvent.keyboard("{ArrowDown}{Enter}");
    expect(onColor).toHaveBeenCalledWith("pink");
  });

  it("picking the applied color goes back to the default, and the highlight toggles", async () => {
    const { onColor, onHighlight } = renderMenu("blue", true);

    await userEvent.click(screen.getByRole("menuitemradio", { name: "Azul" }));
    await userEvent.click(screen.getByRole("menuitemradio", { name: "Marca-texto" }));

    expect(onColor).toHaveBeenCalledWith(null);
    expect(onHighlight).toHaveBeenCalledWith(false);
  });

  it("wraps around and closes on Escape", async () => {
    const { onClose } = renderMenu(null);

    await userEvent.keyboard("{ArrowUp}");
    expect(screen.getByRole("menuitemradio", { name: "Marca-texto" })).toHaveFocus();

    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
  });
});
