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
  respond("GET", "/v1/kbs/kb-1/children", (url) => {
    const parent = url.searchParams.get("parent_id");
    if (parent === "renovacao")
      return { body: [node("docs", "page", "Documentos", "renovacao"), node("t", "file", "Tabela.pdf", "renovacao")] };
    return {
      body: [
        node("emissao", "page", "Emissão de apólice", "residencial"),
        { ...node("renovacao", "page", "Renovação", "residencial"), has_children: true },
        node("auto", "folder", "Auto", "residencial"),
        node("cg", "file", "Condições Gerais 2026.pdf", "residencial"),
      ],
    };
  });
  respond("GET", "/v1/nodes/cg", {
    body: {
      ...node("cg", "file", "Condições Gerais 2026.pdf", "residencial"),
      path: "Residencial/Condições Gerais 2026.pdf",
      page: null,
      file: { size: 2_200_000, mime: "application/pdf", pages: 182, protected: false, sha256: "abc" },
      versions: 1,
    },
  });
});

afterEach(() => vi.unstubAllGlobals());

function renderFolder() {
  return renderInBase(<FolderScreen node={folder} />, "/kbs/kb-1/n/residencial");
}

describe("FolderScreen", () => {
  it("counts its children by kind and filters them", async () => {
    renderFolder();

    expect(await screen.findByRole("button", { name: "Tudo 4" })).toBeInTheDocument();
    expect(screen.getByText("Produto residencial do Bradesco.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Páginas 2" })).toBeInTheDocument();
    const list = screen.getByRole("list");
    const renovacao = within(list).getByRole("link", { name: /Renovação/ });
    expect(await within(renovacao).findByText("2 itens")).toBeInTheDocument();
    const cg = within(list).getByRole("link", { name: /Condições Gerais 2026/ });
    expect(await within(cg).findByText("182 páginas")).toBeInTheDocument();
    expect(cg).toHaveAttribute("href", "/kbs/kb-1/n/cg");

    await userEvent.click(screen.getByRole("button", { name: "Arquivos 1" }));
    expect(within(list).getAllByRole("link")).toHaveLength(1);

    await userEvent.click(screen.getByRole("button", { name: "Páginas 2" }));
    expect(
      within(list)
        .getAllByRole("link")
        .map((link) => link.getAttribute("href")),
    ).toEqual(["/kbs/kb-1/n/emissao", "/kbs/kb-1/n/renovacao"]);
  });

  it("uploads files dropped on it into the folder", async () => {
    renderFolder();
    const zone = await screen.findByText("Solte arquivos aqui para guardar em Residencial");
    const files = [new File(["%PDF"], "Nova.pdf", { type: "application/pdf" })];

    fireEvent.drop(zone, { dataTransfer: { files, types: ["Files"] } });

    await waitFor(() => expect(FakeXhr.sent).toHaveLength(1));
    const [sent] = FakeXhr.sent as [FakeXhr];
    expect(sent.path).toBe("/v1/kbs/kb-1/files");
    expect(sent.form?.get("parent_id")).toBe("residencial");
    expect((sent.form?.get("file") as File).name).toBe("Nova.pdf");
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
});
