import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { I18nProvider } from "../../i18n";
import { ChatPanel } from "./ChatPanel";
import { ShellProvider } from "./shell";

function renderPanel() {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <I18nProvider>
        <ShellProvider>
          {/* Like the editor or an open menu: it handles its own keys and lets none go on. */}
          <div role="textbox" aria-label="Editor" contentEditable tabIndex={0} onKeyDown={(event) => event.stopPropagation()} />
          <ChatPanel />
        </ShellProvider>
      </I18nProvider>
    </MemoryRouter>,
  );
}

const panel = () => screen.queryByRole("complementary", { name: "Chat" });

afterEach(() => vi.unstubAllGlobals());

describe("ChatPanel", () => {
  it("⌘J opens and closes it; outside a base it asks for one", async () => {
    renderPanel();
    expect(panel()).not.toBeInTheDocument();

    await userEvent.keyboard("{Meta>}j{/Meta}");
    expect(panel()).toHaveTextContent("Abra uma base para conversar");

    await userEvent.keyboard("{Meta>}j{/Meta}");
    expect(panel()).not.toBeInTheDocument();
  });

  it("⌘J toggles it with the focus in the editor", async () => {
    renderPanel();
    await userEvent.click(screen.getByRole("textbox", { name: "Editor" }));

    await userEvent.keyboard("{Meta>}j{/Meta}");
    expect(panel()).toBeInTheDocument();
    await userEvent.keyboard("{Meta>}j{/Meta}");
    expect(panel()).not.toBeInTheDocument();
  });

  it("sits beside the page in a wide window and over it in a narrow one", async () => {
    let narrow = false;
    vi.stubGlobal("matchMedia", () => ({ matches: narrow, addEventListener: () => {}, removeEventListener: () => {} }));
    renderPanel();
    await userEvent.keyboard("{Meta>}j{/Meta}");
    expect(panel()).not.toHaveClass("fixed");
    await userEvent.keyboard("{Meta>}j{/Meta}");

    narrow = true;
    await userEvent.keyboard("{Meta>}j{/Meta}");
    expect(panel()).toHaveClass("fixed");
    expect(screen.getByRole("button", { name: "Fechar o chat" })).toBeInTheDocument();
  });
});
