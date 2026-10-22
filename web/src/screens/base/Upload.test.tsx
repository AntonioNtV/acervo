import "@testing-library/jest-dom/vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NodeView } from "../../app/NodeView";
import { node, renderInBase, resetApi, respond } from "../../api/testing";
import { clearUploads, UploadList } from "./Upload";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

class FakeXhr {
  static sent: FakeXhr[] = [];
  upload: { onprogress?: (event: { loaded: number; total: number }) => void } = {};
  onload?: () => void;
  onerror?: () => void;
  status = 0;
  statusText = "";
  response: unknown = null;
  responseType = "";
  form?: FormData;
  method = "";
  path = "";
  headers: Record<string, string> = {};
  open(method: string, path: string) {
    this.method = method;
    this.path = path;
  }
  setRequestHeader(name: string, value: string) {
    this.headers[name] = value;
  }
  send(form: FormData) {
    this.form = form;
    FakeXhr.sent.push(this);
  }
  reply(status: number, body: unknown) {
    this.status = status;
    this.response = body;
    this.onload?.();
  }
}

beforeEach(() => {
  localStorage.clear();
  resetApi();
  clearUploads("kb-1");
  FakeXhr.sent = [];
  vi.stubGlobal("XMLHttpRequest", FakeXhr);
  respond("GET", "/v1/nodes/residencial", {
    body: { ...node("residencial", "folder", "Residencial", "bradesco"), path: "Bradesco/Residencial", page: null, file: null, versions: 0 },
  });
  respond("GET", "/v1/kbs/kb-1/children", { body: [] });
});

afterEach(() => vi.unstubAllGlobals());

function files(...names: string[]) {
  return names.map((name) => new File(["%PDF"], name, { type: "application/pdf" }));
}

describe("Upload", () => {
  it("shows progress per file and where a duplicate already is", async () => {
    renderInBase(
      <>
        <NodeView />
        <UploadList kbId="kb-1" />
      </>,
      "/kbs/kb-1/n/residencial",
    );

    await screen.findByRole("heading", { name: "Residencial" });
    await userEvent.upload(screen.getByLabelText("Enviar arquivos"), files("Nova.pdf", "Condições Gerais 2026.pdf"));

    const [first, second] = FakeXhr.sent as [FakeXhr, FakeXhr];
    expect(first.method).toBe("POST");
    expect(first.path).toBe("/v1/kbs/kb-1/files");
    expect(first.headers["X-API-Key"]).toBe("test-key");
    expect(first.form?.get("parent_id")).toBe("residencial");
    first.upload.onprogress?.({ loaded: 40, total: 100 });
    second.upload.onprogress?.({ loaded: 90, total: 100 });

    const list = screen.getByRole("region", { name: "Envios" });
    const [newRow, dupRow] = within(list).getAllByRole("listitem") as [HTMLElement, HTMLElement];
    expect(await within(newRow).findByText("40%")).toBeInTheDocument();
    expect(within(dupRow).getByText("90%")).toBeInTheDocument();

    second.reply(409, {
      error: "duplicate",
      message: "já está em Bradesco/Auto/Condições Gerais 2026.pdf",
      details: { node_id: "cg", path: "Bradesco/Auto/Condições Gerais 2026.pdf", trashed: false },
    });

    expect(await within(dupRow).findByText(/já está em/)).toBeInTheDocument();
    expect(within(dupRow).getByRole("link", { name: "Bradesco/Auto/Condições Gerais 2026.pdf" })).toHaveAttribute(
      "href",
      "/kbs/kb-1/n/cg",
    );
    expect(within(newRow).getByText("40%")).toBeInTheDocument();
  });

  it("maps a duplicate with history to \"no histórico de\"", async () => {
    renderInBase(
      <>
        <NodeView />
        <UploadList kbId="kb-1" />
      </>,
      "/kbs/kb-1/n/residencial",
    );

    await screen.findByRole("heading", { name: "Residencial" });
    await userEvent.upload(screen.getByLabelText("Enviar arquivos"), files("Antiga.pdf"));
    const [sent] = FakeXhr.sent as [FakeXhr];
    sent.reply(409, {
      error: "duplicate",
      message: "já está no histórico de Bradesco/CG 2026.pdf",
      details: { node_id: "cg", path: "Bradesco/CG 2026.pdf", trashed: false, history: true },
    });

    const row = within(screen.getByRole("region", { name: "Envios" })).getAllByRole("listitem").at(-1) as HTMLElement;
    expect(await within(row).findByText(/já está no histórico de/)).toBeInTheDocument();
    expect(within(row).getByRole("link", { name: "Bradesco/CG 2026.pdf" })).toHaveAttribute("href", "/kbs/kb-1/n/cg");
  });
});
