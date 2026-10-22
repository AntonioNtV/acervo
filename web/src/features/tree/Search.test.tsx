import "@testing-library/jest-dom/vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BaseLayout } from "./BaseLayout";
import { node, renderInBase, resetApi, respond } from "../../testing";

vi.mock("../../api/client", () => import("../../testing").then((m) => m.mockClient()));

beforeEach(() => {
  localStorage.clear();
  resetApi();
  respond("GET", "/kbs", { body: [] });
  respond("GET", "/kbs/kb-1/children", { body: [] });
  respond("GET", "/kbs/kb-1/search", (url) => ({
    body:
      url.searchParams.get("q") === "apolice"
        ? [
            { ...node("emissao", "page", "Emissão de apólice", "residencial"), path: "Bradesco/Residencial/Emissão de apólice" },
            { ...node("apolices", "folder", "Apólices"), path: "Apólices" },
          ]
        : [],
  }));
});

describe("Search", () => {
  it("shows each result with its path", async () => {
    renderInBase(<BaseLayout />);

    await userEvent.type(screen.getByRole("searchbox", { name: "Buscar na base" }), "apolice");

    const page = await screen.findByRole("link", { name: /Emissão de apólice\.md/ });
    expect(page).toHaveTextContent("Bradesco / Residencial");
    expect(page).toHaveAttribute("href", "/kbs/kb-1/n/emissao");
    expect(screen.getByRole("link", { name: "Apólices" })).toBeInTheDocument();
  });
});
