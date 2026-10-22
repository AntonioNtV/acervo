import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nProvider } from "../../i18n";
import { ChatPanel } from "./ChatPanel";
import { ShellProvider } from "./shell";

describe("ChatPanel", () => {
  it("⌘J opens and closes it", async () => {
    render(
      <I18nProvider>
        <ShellProvider>
          <ChatPanel />
        </ShellProvider>
      </I18nProvider>,
    );
    expect(screen.queryByRole("complementary", { name: "Chat" })).not.toBeInTheDocument();

    await userEvent.keyboard("{Meta>}j{/Meta}");
    expect(screen.getByRole("complementary", { name: "Chat" })).toHaveTextContent("Disponível em breve");

    await userEvent.keyboard("{Meta>}j{/Meta}");
    expect(screen.queryByRole("complementary", { name: "Chat" })).not.toBeInTheDocument();
  });
});
