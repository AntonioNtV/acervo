import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { SliderControl } from "./SliderControl";

describe("SliderControl", () => {
  it("reports the new value and writes its label", () => {
    const onChange = vi.fn();
    render(
      <SliderControl
        label="Valor do imóvel"
        value={650}
        min={0}
        max={2600}
        valueLabel="R$ 650 mil"
        onChange={onChange}
      />,
    );
    const slider = screen.getByRole("slider", { name: "Valor do imóvel" });
    expect(slider).toHaveAttribute("aria-valuetext", "R$ 650 mil");
    expect(screen.getByText("R$ 650 mil")).toBeInTheDocument();

    // jsdom does not move a range by its arrows; the browser does, through the same change event.
    fireEvent.change(slider, { target: { value: "1300" } });

    expect(onChange).toHaveBeenCalledWith(1300);
  });

  it("is disabled", () => {
    render(
      <SliderControl
        label="Valor do imóvel"
        value={0}
        min={0}
        max={10}
        valueLabel="R$ 0"
        onChange={vi.fn()}
        disabled
      />,
    );
    expect(screen.getByRole("slider", { name: "Valor do imóvel" })).toBeDisabled();
  });
});
