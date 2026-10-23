import "@testing-library/jest-dom/vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { calls, node, renderWithApi, resetApi, respond } from "../../api/testing";
import { TreeRows } from "./TreeRows";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

const FILE_ID = "44444444-4444-4444-4444-444444444444";

describe("TreeRows", () => {
  it("a failed index shows the error dot, and Tentar de novo builds it again", async () => {
    resetApi();
    respond("GET", "/v1/kbs/kb-1/children", {
      body: [
        { ...node(FILE_ID, "file", "Condições Gerais 2026.pdf"), index_state: "failed" },
        { ...node("page-1", "page", "Prazos"), index_state: "building" },
      ],
    });
    respond("POST", `/v1/nodes/${FILE_ID}/index`, { status: 202, body: node(FILE_ID, "file", "Condições Gerais 2026.pdf") });
    renderWithApi(
      <MemoryRouter>
        <TreeRows kbId="kb-1" draft={null} onDraft={() => {}} />
      </MemoryRouter>,
    );

    const failed = await screen.findByRole("treeitem", { name: "Condições Gerais 2026.pdf" });
    expect(within(failed).getByTitle("A busca não conseguiu ler este item")).toBeInTheDocument();
    expect(within(screen.getByRole("treeitem", { name: "Prazos" })).getByTitle("Preparando a busca")).toBeInTheDocument();

    await userEvent.click(within(failed).getByRole("button", { name: "Ações de Condições Gerais 2026.pdf" }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "Tentar de novo" }));

    await waitFor(() => expect(calls.filter((call) => call.method === "POST" && call.path === `/v1/nodes/${FILE_ID}/index`)).toHaveLength(1));
  });
});
