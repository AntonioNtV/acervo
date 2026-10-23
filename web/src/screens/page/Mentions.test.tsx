import "@testing-library/jest-dom/vitest";
import { screen, waitFor } from "@testing-library/react";
import { calls, nodeFields, renderInBase, resetApi, respond } from "../../api/testing";
import { Mentions } from "./Mentions";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

const linking = {
  ...nodeFields,
  id: "emissao",
  kb_id: "kb-1",
  parent_id: "residencial",
  kind: "page" as const,
  title: "Emissão de apólice",
  deleted_at: null,
  path: "Bradesco/Residencial/Emissão de apólice",
};

beforeEach(() => {
  resetApi();
});

describe("Mentions", () => {
  it("lists each linking page with its path and line, linked to it", async () => {
    respond("GET", "/v1/pages/page-1/mentions", {
      body: [{ node: linking, line: "Renovação aceita até 60 dias após o vencimento. Ver [[Renovação]]." }],
    });
    renderInBase(<Mentions nodeId="page-1" />);

    const mentions = await screen.findByRole("navigation", { name: "Mencionada em" });
    expect(mentions).toHaveTextContent("1 página");
    const link = screen.getByRole("link", { name: /Emissão de apólice/ });
    expect(link).toHaveAttribute("href", "/kbs/kb-1/n/emissao");
    expect(link).toHaveTextContent("Bradesco / Residencial");
    expect(link).toHaveTextContent("Ver [[Renovação]].");
  });

  it("is hidden when no page links here", async () => {
    respond("GET", "/v1/pages/page-1/mentions", { body: [] });
    renderInBase(<Mentions nodeId="page-1" />);

    await waitFor(() => expect(calls.some((call) => call.path === "/v1/pages/page-1/mentions")).toBe(true));
    expect(screen.queryByRole("navigation", { name: "Mencionada em" })).not.toBeInTheDocument();
  });
});
