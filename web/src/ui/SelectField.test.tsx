import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SelectField, type SelectOption } from "./SelectField";

const plans: SelectOption[] = [
  { value: "essencial", label: "Essencial" },
  { value: "completo", label: "Completo" },
  { value: "premium", label: "Premium" },
];

describe("SelectField", () => {
  it("shows the chosen option and picks another by keyboard", async () => {
    const onChange = vi.fn();
    render(<SelectField label="Plano" value="completo" options={plans} onChange={onChange} />);
    const field = screen.getByRole("button", { name: "Plano" });
    expect(field).toHaveTextContent("Completo");

    field.focus();
    await userEvent.keyboard("{Enter}");
    expect(screen.getByRole("menuitemradio", { name: "Completo" })).toHaveAttribute("aria-checked", "true");
    await userEvent.keyboard("{ArrowDown}{ArrowDown}{Enter}");

    expect(onChange).toHaveBeenCalledWith("premium");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("closes on Escape without a change", async () => {
    const onChange = vi.fn();
    render(<SelectField label="Plano" value="completo" options={plans} onChange={onChange} />);

    await userEvent.click(screen.getByRole("button", { name: "Plano" }));
    await userEvent.keyboard("{Escape}");

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("shows a status option with its dot, and does not open when disabled", async () => {
    render(
      <SelectField
        label="Status"
        value="emitida"
        options={[{ value: "emitida", label: "Emitida", tone: "ok" }]}
        onChange={vi.fn()}
        disabled
      />,
    );
    const field = screen.getByRole("button", { name: "Status" });
    expect(field).toHaveTextContent("Emitida");
    expect(field.querySelector(".bg-ok")).not.toBeNull();

    await userEvent.click(field);
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});
