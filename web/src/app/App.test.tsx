import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
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
  it("renders the base frame with the chat disabled", () => {
    renderAt("/kbs/kb-1/n/node-1");

    const chat = screen.getByRole("complementary", { name: "Chat" });
    expect(chat).toHaveTextContent("disponível em breve");
    expect(screen.getByRole("textbox", { name: "Mensagem" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Capturar" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Perguntar" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Enviar" })).toBeDisabled();
  });

  it("switching theme changes the root class", async () => {
    renderAt("/");

    await userEvent.click(screen.getByRole("button", { name: "Escuro" }));
    expect(document.documentElement).toHaveClass("dark");

    await userEvent.click(screen.getByRole("button", { name: "Claro" }));
    expect(document.documentElement).not.toHaveClass("dark");
  });

  it("switching language changes the nav labels", async () => {
    renderAt("/");
    const nav = screen.getByRole("complementary", { name: "Navegação" });
    expect(nav).toHaveTextContent("Lixeira");

    await userEvent.click(screen.getByRole("button", { name: "EN" }));

    expect(screen.getByRole("link", { name: "Trash" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Lixeira" })).not.toBeInTheDocument();
  });
});
