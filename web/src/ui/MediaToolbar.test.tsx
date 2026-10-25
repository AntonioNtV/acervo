import "@testing-library/jest-dom/vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nProvider } from "../i18n";
import { MediaToolbar } from "./MediaToolbar";

beforeEach(() => localStorage.clear());

describe("MediaToolbar", () => {
  it("shows the tools it is given and reports the one used, by click or keyboard", async () => {
    const onAction = vi.fn();
    render(
      <I18nProvider>
        <MediaToolbar tools={["replace", "download", "open"]} onAction={onAction} />
      </I18nProvider>,
    );
    const bar = screen.getByRole("toolbar", { name: "Mídia" });

    expect(within(bar).getAllByRole("button").map((button) => button.getAttribute("aria-label"))).toEqual([
      "Substituir",
      "Baixar",
      "Abrir",
    ]);

    await userEvent.click(within(bar).getByRole("button", { name: "Baixar" }));
    await userEvent.keyboard("{ArrowRight}{Enter}");
    await userEvent.keyboard("{ArrowRight}{ArrowRight}{Enter}");

    expect(onAction.mock.calls).toEqual([["download"], ["open"], ["download"]]);
  });
});
