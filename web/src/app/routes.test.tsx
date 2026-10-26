import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { node, resetApi, respond } from "../api/testing";
import { fakeBases, summary } from "../screens/bases/testing";
import { Providers } from "./Providers";
import { routes } from "./routes";

vi.mock("../api/client", () => import("../api/testing").then((m) => m.mockClient()));

beforeEach(() => {
  localStorage.clear();
  resetApi();
});

function renderHome(path = "/") {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <Providers>
      <RouterProvider router={router} />
    </Providers>,
  );
  return router;
}

describe("routes", () => {
  it("/ goes to the last page seen", async () => {
    fakeBases([summary({ id: "kb-1", name: "Seguros" })]);
    localStorage.setItem("acervo.lastPage", "/kbs/kb-1/n/renovacao");
    respond("GET", "/v1/nodes/renovacao", { body: node("renovacao", "page", "Renovação") });

    const router = renderHome();

    await waitFor(() => expect(router.state.location.pathname).toBe("/kbs/kb-1/n/renovacao"));
  });

  it("a last page that moved to another base opens under its new base", async () => {
    fakeBases([summary({ id: "kb-1", name: "Seguros" }), summary({ id: "kb-2", name: "Saúde" })]);
    localStorage.setItem("acervo.lastPage", "/kbs/kb-1/n/renovacao");
    respond("GET", "/v1/nodes/renovacao", { body: { ...node("renovacao", "page", "Renovação"), kb_id: "kb-2" } });

    const router = renderHome();

    await waitFor(() => expect(router.state.location.pathname).toBe("/kbs/kb-2/n/renovacao"));
  });

  it("a last page that is gone is forgotten, and / goes to the first base's first node", async () => {
    fakeBases([summary({ id: "kb-1", name: "Seguros" })]);
    localStorage.setItem("acervo.lastPage", "/kbs/kb-1/n/apagada");
    respond("GET", "/v1/kbs/kb-1/children", { body: [node("bradesco", "folder", "Bradesco")] });

    const router = renderHome();

    await waitFor(() => expect(router.state.location.pathname).toBe("/kbs/kb-1/n/bradesco"));
    expect(localStorage.getItem("acervo.lastPage")).not.toBe("/kbs/kb-1/n/apagada");
  });

  it("with no page seen, / goes to the first base's first node", async () => {
    fakeBases([summary({ id: "kb-1", name: "Seguros" }), summary({ id: "kb-2", name: "Pessoal" })]);
    respond("GET", "/v1/kbs/kb-1/children", (url) => ({
      body: url.searchParams.get("parent_id") ? [] : [node("bradesco", "folder", "Bradesco"), node("glossario", "page", "Glossário")],
    }));

    const router = renderHome();

    await waitFor(() => expect(router.state.location.pathname).toBe("/kbs/kb-1/n/bradesco"));
  });

  it("a 401 from any query forgets this browser's pages and sends to Entrar with the way back", async () => {
    fakeBases([summary({ id: "kb-1", name: "Seguros" })]);
    localStorage.setItem("acervo.lastPage", "/kbs/kb-1/n/renovacao");
    localStorage.setItem("acervo.recent.kb-1", JSON.stringify(["renovacao"]));
    respond("GET", "/v1/nodes/renovacao", { status: 401, body: { error: "unauthorized", message: "no session" } });

    const router = renderHome("/kbs/kb-1/n/renovacao?p=2");

    await waitFor(() => expect(router.state.location.pathname).toBe("/entrar"));
    expect(router.state.location.search).toBe(`?next=${encodeURIComponent("/kbs/kb-1/n/renovacao?p=2")}`);
    expect(await screen.findByRole("heading", { name: "Entrar no Acervo" })).toBeInTheDocument();
    expect(localStorage.getItem("acervo.lastPage")).toBeNull();
    expect(localStorage.getItem("acervo.recent.kb-1")).toBeNull();
  });

  it("a 401 sends the theme and language back to the browser's", async () => {
    fakeBases([summary({ id: "kb-1", name: "Seguros" })]);
    localStorage.setItem("acervo.theme", "dark");
    localStorage.setItem("acervo.lang", "en");
    respond("GET", "/v1/nodes/renovacao", { status: 401, body: { error: "unauthorized", message: "no session" } });

    const router = renderHome("/kbs/kb-1/n/renovacao");

    await waitFor(() => expect(router.state.location.pathname).toBe("/entrar"));
    expect(await screen.findByRole("heading", { name: "Entrar no Acervo" })).toBeInTheDocument();
    expect(localStorage.getItem("acervo.theme")).toBe("system");
    expect(localStorage.getItem("acervo.lang")).toBe("ptBR");
    expect(document.documentElement).not.toHaveClass("dark");
  });

  it("with no base, / offers a new one", async () => {
    fakeBases([]);

    renderHome();

    expect(await screen.findByText("Nenhuma base ainda. Crie a primeira.")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Nova base" })).toHaveLength(2);
  });
});
