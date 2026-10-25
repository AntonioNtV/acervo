import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nProvider } from "../i18n";
import { TemplateEditor } from "./TemplateEditor";

function renderEditor(label: string) {
  const onChange = vi.fn();
  const onClose = vi.fn();
  render(
    <I18nProvider>
      <TemplateEditor
        label={label}
        lines={["Pedir vistoria do imóvel", "Avisar a corretora"]}
        onChange={onChange}
        onClose={onClose}
      />
    </I18nProvider>,
  );
  return { onChange, onClose, field: screen.getByRole("textbox", { name: "Rótulo" }) };
}

beforeEach(() => localStorage.clear());

describe("TemplateEditor", () => {
  it("edits the label and shows the template", async () => {
    const { onChange, field } = renderEditor("Nova vistoria");
    expect(screen.getByText("Avisar a corretora")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    await userEvent.type(field, "!");
    expect(onChange).toHaveBeenLastCalledWith("Nova vistoria!");
  });

  it("is invalid without a label and closes on Escape", async () => {
    const { onClose, field } = renderEditor("");
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent("Dê um rótulo ao botão.");

    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
  });
});
