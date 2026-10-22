import "@testing-library/jest-dom/vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { NodeDetail } from "../../api/queries";
import { NodeView } from "../../app/NodeView";
import { calls, renderInBase, resetApi, respond } from "../../testing";
import { openPdf, type OnPassword } from "./pdfjs";

vi.mock("../../api/client", () => import("../../testing").then((m) => m.mockClient()));
vi.mock("./pdfjs", () => ({ openPdf: vi.fn() }));

const NODE_ID = "22222222-2222-2222-2222-222222222222";
const PASSWORD = "s3gredo-da-apolice";

const node: NodeDetail = {
  id: NODE_ID,
  kb_id: "kb-1",
  parent_id: null,
  kind: "file",
  title: "Contrato.pdf",
  deleted_at: null,
  path: "Contrato.pdf",
  page: null,
  file: { size: 1000, mime: "application/pdf", pages: null, protected: true, sha256: "abc" },
  versions: 1,
};

describe("a protected PDF", () => {
  it("asks its password in a dialog and hands it to pdf.js only", async () => {
    resetApi();
    respond("GET", `/nodes/${NODE_ID}`, { body: node });
    const xhrOpen = vi.spyOn(XMLHttpRequest.prototype, "open");
    const xhrSend = vi.spyOn(XMLHttpRequest.prototype, "send");
    const submit = vi.fn();
    vi.mocked(openPdf).mockImplementation((_url, onPassword: OnPassword) => {
      onPassword(submit, false);
      return { promise: new Promise(() => {}), destroy: () => {} };
    });

    renderInBase(<NodeView />, `/kbs/kb-1/n/${NODE_ID}`);

    const dialog = await screen.findByRole("dialog", { name: "Este PDF tem senha" });
    await userEvent.type(screen.getByLabelText("Senha"), PASSWORD);
    await userEvent.click(screen.getByRole("button", { name: "Abrir" }));

    expect(submit).toHaveBeenCalledWith(PASSWORD);
    expect(dialog).not.toBeInTheDocument();
    expect(calls.length).toBeGreaterThan(0);
    expect(JSON.stringify(calls)).not.toContain(PASSWORD);
    expect(JSON.stringify(xhrOpen.mock.calls)).not.toContain(PASSWORD);
    expect(xhrSend).not.toHaveBeenCalled();
    expect(JSON.stringify({ ...localStorage })).not.toContain(PASSWORD);
  });
});
