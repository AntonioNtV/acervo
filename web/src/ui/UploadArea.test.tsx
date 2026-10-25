import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { I18nProvider } from "../i18n";
import { UploadArea } from "./UploadArea";

function renderArea(props: Partial<ComponentProps<typeof UploadArea>> = {}) {
  const onFiles = vi.fn();
  const onRetry = vi.fn();
  const { container } = render(
    <I18nProvider>
      <UploadArea kind="file" onFiles={onFiles} onRetry={onRetry} {...props} />
    </I18nProvider>,
  );
  return { onFiles, onRetry, area: container.firstElementChild as HTMLElement };
}

beforeEach(() => localStorage.clear());

describe("UploadArea", () => {
  it("sends the files picked with Enviar or dropped on it", async () => {
    const { onFiles, area } = renderArea();
    const picked = new File(["a"], "Tabela de franquias.xlsx");
    const dropped = new File(["b"], "Apólice.docx");

    await userEvent.upload(screen.getByLabelText("Envie um arquivo"), picked);
    fireEvent.drop(area, { dataTransfer: { files: [dropped] } });

    expect(onFiles.mock.calls).toEqual([[[picked]], [[dropped]]]);
    expect(screen.getByRole("button", { name: "Enviar" })).toBeInTheDocument();
  });

  it("shows the progress while it uploads", () => {
    renderArea({ progress: 42, name: "Tabela de franquias.xlsx" });

    expect(screen.getByText("Enviando… 42%")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Tabela de franquias.xlsx" })).toHaveAttribute("aria-valuenow", "42");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("says what went wrong and tries again", async () => {
    const { onRetry } = renderArea({ kind: "image", error: "A imagem passa de 20 MB. Envie uma menor." });

    expect(screen.getByRole("alert")).toHaveTextContent("A imagem passa de 20 MB. Envie uma menor.");
    await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));

    expect(onRetry).toHaveBeenCalledOnce();
  });
});
