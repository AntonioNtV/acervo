import "@testing-library/jest-dom/vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { resetApi } from "../../testing";
import { fakeBases, renderPage, summary } from "./testing";
import { TrashPage } from "./TrashPage";

vi.mock("../../api/client", () => import("../../testing").then((m) => m.mockClient()));

let kbs: ReturnType<typeof fakeBases>;

beforeEach(() => {
  localStorage.clear();
  const yesterday = new Date(Date.now() - 26 * 3600 * 1000).toISOString();
  resetApi();
  kbs = fakeBases([
    summary({ id: "kb-1", name: "Pessoal", deleted_at: yesterday }),
    summary({ id: "kb-2", name: "Lab de extração de PDF", deleted_at: yesterday }),
  ]);
});

describe("TrashPage", () => {
  it("restoring removes it from the trash list", async () => {
    renderPage(<TrashPage />);
    const row = (await screen.findByText("Pessoal")).closest("li")!;
    expect(row).toHaveTextContent("Movida para a Lixeira ontem");

    await userEvent.click(within(row).getByRole("button", { name: "Restaurar" }));

    await screen.findByRole("heading", { name: "Lixeira 1" });
    expect(screen.queryByText("Pessoal")).not.toBeInTheDocument();
    expect(screen.getByText("Lab de extração de PDF")).toBeInTheDocument();
    expect(kbs.find((kb) => kb.id === "kb-1")?.deleted_at).toBeNull();
  });
});
