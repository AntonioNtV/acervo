import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { MapPin } from "./MapPin";

function renderPin() {
  const onSelect = vi.fn();
  const onClose = vi.fn();
  function Controlled() {
    const [selected, setSelected] = useState(false);
    return (
      <MapPin
        label="Campinas"
        selected={selected}
        title="Marina Couto"
        meta="Campinas · Lince Corretora"
        status={{ label: "Emitida", tone: "ok" }}
        value="R$ 1.284,00"
        onSelect={() => (onSelect(), setSelected(true))}
        onClose={() => (onClose(), setSelected(false))}
      />
    );
  }
  render(<Controlled />);
  return { onSelect, onClose };
}

describe("MapPin", () => {
  it("opens its popover when selected and closes on Escape", async () => {
    const { onSelect, onClose } = renderPin();
    const pin = screen.getByRole("button", { name: "Marina Couto" });
    expect(screen.queryByText("Emitida")).not.toBeInTheDocument();

    await userEvent.click(pin);
    expect(onSelect).toHaveBeenCalledOnce();
    expect(pin).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("R$ 1.284,00")).toBeInTheDocument();

    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
    expect(screen.queryByText("Emitida")).not.toBeInTheDocument();
  });
});
