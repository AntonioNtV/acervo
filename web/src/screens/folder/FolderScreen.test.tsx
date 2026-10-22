import "@testing-library/jest-dom/vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { NodeDetail } from "../../api/client";
import { calls, node, renderInBase, resetApi, respond } from "../../api/testing";
import { clearUploads } from "../base/Upload";
import { FolderScreen } from "./FolderScreen";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

const folder: NodeDetail = {
  ...node("residencial", "folder", "Residencial", null),
  description: "Produto residencial do Bradesco.",
  path: "Residencial",
  page: null,
  file: null,
  versions: 0,
};

class FakeXhr {
  static sent: FakeXhr[] = [];
  upload = {};
  form?: FormData;
  path = "";
  open(_method: string, path: string) {
    this.path = path;
  }
  setRequestHeader() {}
  send(form: FormData) {
    this.form = form;
    FakeXhr.sent.push(this);
  }
}

beforeEach(() => {
  localStorage.clear();
  resetApi();
  clearUploads("kb-1");
  FakeXhr.sent = [];
  vi.stubGlobal("XMLHttpRequest", FakeXhr);
  respond("GET", "/v1/nodes/residencial", { body: folder });
  respond("GET", "/v1/kbs/kb-1/children", {
    body: [
      node("emissao", "page", "Emissão de apólice", "residencial"),
      { ...node("renovacao", "page", "Renovação", "residencial"), child_count: 2 },
      node("auto", "folder", "Auto", "residencial"),
      { ...node("cg", "file", "Condições Gerais 2026.pdf", "residencial"), pages: 182, size: 2_200_000 },
    ],
  });
});

afterEach(() => vi.unstubAllGlobals());

function renderFolder() {
  return renderInBase(<FolderScreen node={folder} />, "/kbs/kb-1/n/residencial");
}

describe("FolderScreen", () => {
  it("lists its children as links with what they hold", async () => {
    renderFolder();

    expect(await screen.findByText("Produto residencial do Bradesco.")).toBeInTheDocument();
    const list = screen.getByRole("list");
    expect((await within(list).findAllByRole("link")).map((link) => link.getAttribute("href"))).toEqual([
      "/kbs/kb-1/n/emissao",
      "/kbs/kb-1/n/renovacao",
      "/kbs/kb-1/n/auto",
      "/kbs/kb-1/n/cg",
    ]);
    expect(within(within(list).getByRole("link", { name: /Renovação/ })).getByText("2 itens")).toBeInTheDocument();
    expect(
      within(within(list).getByRole("link", { name: /Condições Gerais 2026/ })).getByText("182 páginas"),
    ).toBeInTheDocument();
  });

  it("uploads files dropped on it into the folder", async () => {
    renderFolder();
    const title = await screen.findByRole("heading", { name: "Residencial" });
    const files = [new File(["%PDF"], "Nova.pdf", { type: "application/pdf" })];

    fireEvent.dragOver(title, { dataTransfer: { files, types: ["Files"] } });
    expect(screen.getByText("Solte arquivos aqui para guardar em Residencial")).toBeInTheDocument();
    fireEvent.drop(title, { dataTransfer: { files, types: ["Files"] } });

    await waitFor(() => expect(FakeXhr.sent).toHaveLength(1));
    const [sent] = FakeXhr.sent as [FakeXhr];
    expect(sent.path).toBe("/v1/kbs/kb-1/files");
    expect(sent.form?.get("parent_id")).toBe("residencial");
    expect((sent.form?.get("file") as File).name).toBe("Nova.pdf");
    expect(screen.queryByText("Solte arquivos aqui para guardar em Residencial")).not.toBeInTheDocument();
  });

  it("renames the folder in place", async () => {
    respond("PATCH", "/v1/nodes/residencial", { body: { ...folder, title: "Residencial Plus" } });
    renderFolder();

    await userEvent.click(await screen.findByRole("button", { name: "Renomear Residencial" }));
    const input = screen.getByRole("textbox", { name: "Renomear Residencial" });
    await userEvent.clear(input);
    await userEvent.type(input, "Residencial Plus{Enter}");

    await waitFor(() =>
      expect(calls.find((call) => call.method === "PATCH")?.body).toEqual({ title: "Residencial Plus" }),
    );
  });

  it("edits the description in place", async () => {
    respond("PATCH", "/v1/nodes/residencial", { body: { ...folder, description: "Emissão e renovação." } });
    renderFolder();

    await userEvent.click(await screen.findByRole("button", { name: "Produto residencial do Bradesco." }));
    const input = screen.getByRole("textbox", { name: "Adicionar uma descrição" });
    await userEvent.clear(input);
    await userEvent.type(input, "Emissão e renovação.{Enter}");

    await waitFor(() =>
      expect(calls.find((call) => call.method === "PATCH")?.body).toEqual({ description: "Emissão e renovação." }),
    );
  });
});
