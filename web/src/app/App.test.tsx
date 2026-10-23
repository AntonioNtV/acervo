import "@testing-library/jest-dom/vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App";

vi.mock("../api/client", () => import("../api/testing").then((m) => m.mockClient()));

function renderAt(path: string) {
  window.history.pushState({}, "", path);
  return render(<App />);
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.className = "";
});

describe("App", () => {
  it("opens the chat from the top bar, with one box and no modes", async () => {
    renderAt("/lixeira");

    await userEvent.click(screen.getByRole("button", { name: "Chat" }));

    const chat = screen.getByRole("complementary", { name: "Chat" });
    expect(chat).toHaveTextContent("Abra uma base para conversar");
    expect(within(chat).queryByRole("button", { name: "Capturar" })).not.toBeInTheDocument();
  });

  it("switching theme changes the root class", async () => {
    renderAt("/lixeira");

    await userEvent.click(screen.getByRole("button", { name: "Escuro" }));
    expect(document.documentElement).toHaveClass("dark");

    await userEvent.click(screen.getByRole("button", { name: "Claro" }));
    expect(document.documentElement).not.toHaveClass("dark");
  });

  it("switching language changes the nav labels", async () => {
    renderAt("/lixeira");
    const nav = screen.getByRole("navigation", { name: "Navegação" });
    expect(nav).toHaveTextContent("Lixeira");

    await userEvent.click(screen.getByRole("button", { name: "EN" }));

    expect(screen.getByRole("link", { name: "Trash" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Lixeira" })).not.toBeInTheDocument();
  });
});
