import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nProvider } from "../i18n";
import { SyncedFrame } from "./SyncedFrame";

function renderFrame(error?: boolean) {
  const onEdit = vi.fn();
  const onUnlink = vi.fn();
  render(
    <I18nProvider>
      <SyncedFrame source="Renovação.md › Documentos" error={error} onEdit={onEdit} onUnlink={onUnlink}>
        <p>Boleto da 1ª parcela no portal no mesmo dia.</p>
      </SyncedFrame>
    </I18nProvider>,
  );
  return { onEdit, onUnlink };
}

beforeEach(() => localStorage.clear());

describe("SyncedFrame", () => {
  it("shows the content and edits at the source", async () => {
    const { onEdit } = renderFrame();

    expect(screen.getByText("Boleto da 1ª parcela no portal no mesmo dia.")).toBeInTheDocument();
    expect(screen.getByText(/de Renovação\.md › Documentos/)).toBeInTheDocument();
    await userEvent.tab();
    await userEvent.keyboard("{Enter}");

    expect(onEdit).toHaveBeenCalledOnce();
  });

  it("says the source is gone and unlinks", async () => {
    const { onEdit, onUnlink } = renderFrame(true);

    expect(screen.getByRole("alert")).toHaveTextContent("A seção de origem foi apagada.");
    expect(screen.queryByText("Boleto da 1ª parcela no portal no mesmo dia.")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Editar na origem" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Desvincular" }));

    expect(onUnlink).toHaveBeenCalledOnce();
    expect(onEdit).not.toHaveBeenCalled();
  });
});
