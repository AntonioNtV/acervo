import "@testing-library/jest-dom/vitest";
import { act, screen } from "@testing-library/react";
import { pageNode, versions } from "../screens/page/testing";
import { renderInBase, resetApi, respond } from "../api/testing";
import { NodeView } from "./NodeView";

vi.mock("../api/client", () => import("../api/testing").then((m) => m.mockClient()));

beforeEach(() => {
  localStorage.clear();
  resetApi();
  respond("GET", "/v1/pages/page-1/versions", { body: versions });
});

describe("NodeView", () => {
  it("a failed refetch keeps the page", async () => {
    respond("GET", "/v1/nodes/page-1", { body: pageNode() });
    const { queryClient } = renderInBase(<NodeView />, "/kbs/kb-1/n/page-1");
    expect(await screen.findByRole("heading", { name: "Emissão de apólice" })).toBeInTheDocument();

    respond("GET", "/v1/nodes/page-1", { status: 500, body: "Internal Server Error" });
    await act(() => queryClient.refetchQueries({ queryKey: ["node", "page-1"] }));

    expect(queryClient.getQueryState(["node", "page-1"])?.status).toBe("error");
    expect(screen.getByRole("heading", { name: "Emissão de apólice" })).toBeInTheDocument();
    expect(screen.queryByText(/servidor/)).not.toBeInTheDocument();
  });

  it("a 404 shows the translated message", async () => {
    respond("GET", "/v1/nodes/page-1", {
      status: 404,
      body: { error: "not_found", message: "node page-1 not found" },
    });
    renderInBase(<NodeView />, "/kbs/kb-1/n/page-1");

    expect(await screen.findByText("Não encontrado: não existe ou foi para a Lixeira.")).toBeInTheDocument();
    expect(screen.queryByText(/node page-1/)).not.toBeInTheDocument();
  });

  it("a refused session says so in its own words", async () => {
    respond("GET", "/v1/nodes/page-1", {
      status: 401,
      body: { error: "unauthorized", message: "Missing or expired session." },
    });
    renderInBase(<NodeView />, "/kbs/kb-1/n/page-1");

    expect(await screen.findByText("Sua sessão terminou. Entre de novo.")).toBeInTheDocument();
    expect(screen.queryByText(/Missing/)).not.toBeInTheDocument();
  });
});
