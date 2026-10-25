import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nProvider } from "../i18n";
import { SwitchControl } from "./SwitchControl";

function renderSwitch(checked: boolean, disabled?: boolean) {
  const onChange = vi.fn();
  render(
    <I18nProvider>
      <SwitchControl label="Teve sinistro" checked={checked} onChange={onChange} disabled={disabled} />
    </I18nProvider>,
  );
  return {
    onChange,
    toggle: screen.getByRole("switch", { name: "Teve sinistro" }),
  };
}

beforeEach(() => localStorage.clear());

describe("SwitchControl", () => {
  it("writes Não when off and turns on by click or Space", async () => {
    const { onChange, toggle } = renderSwitch(false);
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(screen.getByText("Não")).toBeInTheDocument();

    await userEvent.click(toggle);
    await userEvent.keyboard(" ");

    expect(onChange.mock.calls).toEqual([[true], [true]]);
  });

  it("writes Sim when on and turns off", async () => {
    const { onChange, toggle } = renderSwitch(true);
    expect(screen.getByText("Sim")).toBeInTheDocument();

    await userEvent.click(toggle);

    expect(onChange).toHaveBeenCalledWith(false);
  });

  it("does nothing when disabled", async () => {
    const { onChange, toggle } = renderSwitch(false, true);
    await userEvent.click(toggle);
    expect(onChange).not.toHaveBeenCalled();
  });
});
