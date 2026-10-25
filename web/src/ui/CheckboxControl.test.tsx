import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CheckboxControl } from "./CheckboxControl";

describe("CheckboxControl", () => {
  it("toggles from its label", async () => {
    const onChange = vi.fn();
    render(
      <CheckboxControl checked onChange={onChange}>
        Incluir danos elétricos
      </CheckboxControl>,
    );
    expect(screen.getByRole("checkbox", { name: "Incluir danos elétricos" })).toBeChecked();

    await userEvent.click(screen.getByText("Incluir danos elétricos"));

    expect(onChange).toHaveBeenCalledWith(false);
  });

  it("does nothing when disabled", async () => {
    const onChange = vi.fn();
    render(
      <CheckboxControl checked={false} onChange={onChange} disabled>
        Incluir danos elétricos
      </CheckboxControl>,
    );

    await userEvent.click(screen.getByText("Incluir danos elétricos"));

    expect(onChange).not.toHaveBeenCalled();
  });
});
