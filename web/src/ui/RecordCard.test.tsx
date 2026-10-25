import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nProvider } from "../i18n";
import { RecordCard } from "./RecordCard";

beforeEach(() => localStorage.clear());

describe("RecordCard", () => {
  it("opens by click or Enter and looks lifted while dragged", async () => {
    const onOpen = vi.fn();
    const onDragStart = vi.fn();
    render(
      <I18nProvider>
        <RecordCard
          variant="board"
          title="Marina Couto"
          meta="Campinas · Lince Corretora"
          value="R$ 1.284,00"
          onOpen={onOpen}
          onDragStart={onDragStart}
        />
      </I18nProvider>,
    );
    const card = screen.getByRole("button", { name: /Marina Couto/ });

    await userEvent.click(card);
    await userEvent.keyboard("{Enter}");
    expect(onOpen).toHaveBeenCalledTimes(2);

    fireEvent.dragStart(card);
    expect(onDragStart).toHaveBeenCalledOnce();
    expect(card).toHaveClass("bg-accent-soft");
    fireEvent.dragEnd(card);
    expect(card).not.toHaveClass("bg-accent-soft");
  });

  it("shows the status in the gallery and the drop place", () => {
    render(
      <I18nProvider>
        <RecordCard variant="gallery" title="Marina Couto" status={{ label: "Emitida", tone: "ok" }} onOpen={() => {}} />
        <RecordCard variant="drop" />
      </I18nProvider>,
    );

    expect(screen.getByText("Emitida")).toBeInTheDocument();
    expect(screen.getByText("Soltar aqui")).toBeInTheDocument();
  });
});
