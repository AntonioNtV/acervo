import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nProvider } from "../i18n";
import { PropertyEditor, type PropertyType } from "./PropertyEditor";

const OPTIONS = [
  { label: "Em emissão", tone: "run" as const },
  { label: "Emitida", tone: "ok" as const },
];

function renderEditor(type: PropertyType = "select") {
  const onChange = vi.fn();
  const onAddOption = vi.fn();
  const onClose = vi.fn();
  render(
    <I18nProvider>
      <PropertyEditor
        name="Status"
        type={type}
        options={OPTIONS}
        onChange={onChange}
        onAddOption={onAddOption}
        onClose={onClose}
      />
    </I18nProvider>,
  );
  return { onChange, onAddOption, onClose };
}

beforeEach(() => localStorage.clear());

describe("PropertyEditor", () => {
  it("renames, changes the type and adds an option", async () => {
    const { onChange, onAddOption } = renderEditor();
    expect(screen.getByText("Em emissão")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("textbox", { name: "Nome da propriedade" }), { target: { value: "Situação" } });
    expect(onChange).toHaveBeenLastCalledWith({ name: "Situação", type: "select" });

    await userEvent.click(screen.getByRole("button", { name: "Tipo · Seleção" }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "Data" }));
    expect(onChange).toHaveBeenLastCalledWith({ name: "Status", type: "date" });

    await userEvent.click(screen.getByRole("button", { name: "+ Nova opção" }));
    expect(onAddOption).toHaveBeenCalledOnce();
  });

  it("lists options only for a select, and closes on Escape", async () => {
    const { onClose } = renderEditor("text");
    expect(screen.queryByText("Em emissão")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "+ Nova opção" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("textbox", { name: "Nome da propriedade" }));
    await userEvent.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalledOnce();
  });
});
