import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nProvider } from "../i18n";
import { RatingControl } from "./RatingControl";

function renderRating(value: number) {
  const onChange = vi.fn();
  render(
    <I18nProvider>
      <RatingControl label="Avaliação" value={value} onChange={onChange} />
    </I18nProvider>,
  );
  return {
    onChange,
    group: screen.getByRole("radiogroup", { name: "Avaliação" }),
  };
}

beforeEach(() => localStorage.clear());

describe("RatingControl", () => {
  it("picks a star by click and clears when the chosen one is clicked again", async () => {
    const { onChange } = renderRating(4);
    expect(screen.getByRole("radio", { name: "4 estrelas" })).toBeChecked();

    await userEvent.click(screen.getByRole("radio", { name: "2 estrelas" }));
    await userEvent.click(screen.getByRole("radio", { name: "4 estrelas" }));

    expect(onChange.mock.calls).toEqual([[2], [0]]);
  });

  it("moves by arrows from the chosen star, down to 0", async () => {
    const { onChange } = renderRating(1);

    await userEvent.tab();
    expect(screen.getByRole("radio", { name: "1 estrela" })).toHaveFocus();
    await userEvent.keyboard("{ArrowRight}");
    expect(onChange).toHaveBeenLastCalledWith(2);
    await userEvent.keyboard("{ArrowLeft}");

    expect(onChange).toHaveBeenLastCalledWith(0);
  });
});
