import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nProvider } from "../i18n";
import { FormulaEditor } from "./FormulaEditor";

function renderEditor(error?: string) {
  const onChange = vi.fn();
  const onClose = vi.fn();
  const onCancel = vi.fn();
  render(
    <I18nProvider>
      <FormulaEditor
        kind="tex"
        source="P = V \times t"
        error={error}
        onChange={onChange}
        onClose={onClose}
        onCancel={onCancel}
      />
    </I18nProvider>,
  );
  return { onChange, onClose, onCancel, source: screen.getByRole("textbox", { name: "Fonte da fórmula" }) };
}

beforeEach(() => localStorage.clear());

describe("FormulaEditor", () => {
  it("previews the source, reports typing and closes on Enter", async () => {
    const { onChange, onClose, source } = renderEditor();
    expect(screen.getByText("P = V × t")).toBeInTheDocument();
    expect(source).toHaveFocus();

    await userEvent.type(source, "x");
    expect(onChange).toHaveBeenLastCalledWith("P = V \\times tx");

    await userEvent.keyboard("{Enter}");
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("shows the error, keeps it open on Enter and cancels on Escape", async () => {
    const { onClose, onCancel, source } = renderEditor("Equação inválida: uma chave sem par.");
    expect(screen.getByRole("alert")).toHaveTextContent("Equação inválida: uma chave sem par.");
    expect(source).toHaveAttribute("aria-invalid", "true");
    expect(screen.queryByText("P = V × t")).not.toBeInTheDocument();

    await userEvent.keyboard("{Enter}{Escape}");
    expect(onClose).not.toHaveBeenCalled();
    expect(onCancel).toHaveBeenCalledOnce();
  });
});
