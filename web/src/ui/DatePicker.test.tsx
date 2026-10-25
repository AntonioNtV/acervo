import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nProvider } from "../i18n";
import { DatePicker } from "./DatePicker";

function renderPicker(props: Partial<Parameters<typeof DatePicker>[0]> = {}) {
  const onChange = vi.fn();
  const onClose = vi.fn();
  render(
    <I18nProvider>
      <DatePicker mode="single" value="2026-11-15" today="2026-11-10" onChange={onChange} onClose={onClose} {...props} />
    </I18nProvider>,
  );
  return { onChange, onClose };
}

beforeEach(() => localStorage.clear());

describe("DatePicker", () => {
  it("shows the month in pt-BR, marks the day and today, and picks by click", async () => {
    const { onChange } = renderPicker();

    expect(screen.getByText("Novembro de 2026")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "15 de novembro de 2026" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "10 de novembro de 2026" })).toHaveAttribute("aria-current", "date");

    await userEvent.click(screen.getByRole("button", { name: "20 de novembro de 2026" }));
    expect(onChange).toHaveBeenCalledWith("2026-11-20", null);
  });

  it("moves by arrows across months and picks with Enter; Escape closes", async () => {
    const { onChange, onClose } = renderPicker({ value: "2026-11-02" });
    expect(screen.getByRole("button", { name: "2 de novembro de 2026" })).toHaveFocus();

    await userEvent.keyboard("{ArrowUp}");
    expect(await screen.findByText("Outubro de 2026")).toBeInTheDocument();
    await vi.waitFor(() => expect(screen.getByRole("button", { name: "26 de outubro de 2026" })).toHaveFocus());

    await userEvent.keyboard("{Enter}{Escape}");
    expect(onChange).toHaveBeenCalledWith("2026-10-26", null);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("navigates months with the buttons", async () => {
    renderPicker();
    await userEvent.click(screen.getByRole("button", { name: "Próximo mês" }));
    expect(screen.getByText("Dezembro de 2026")).toBeInTheDocument();
  });

  it("ends a started period on the second day, in order", async () => {
    const { onChange } = renderPicker({ mode: "range", value: "2026-11-15", end: null });
    await userEvent.click(screen.getByRole("button", { name: "9 de novembro de 2026" }));
    expect(onChange).toHaveBeenCalledWith("2026-11-09", "2026-11-15");
  });

  it("starts a new period when one is complete", async () => {
    const { onChange } = renderPicker({ mode: "range", value: "2026-11-15", end: "2026-11-21" });
    expect(screen.getByRole("button", { name: "21 de novembro de 2026" })).toHaveAttribute("aria-pressed", "true");

    await userEvent.click(screen.getByRole("button", { name: "25 de novembro de 2026" }));
    expect(onChange).toHaveBeenCalledWith("2026-11-25", null);
  });

  it("toggles the reminder when the date can carry one", async () => {
    const onReminder = vi.fn();
    renderPicker({ reminder: false, onReminder });
    await userEvent.click(screen.getByRole("switch", { name: "Lembrar no dia" }));
    expect(onReminder).toHaveBeenCalledWith(true);
  });
});
