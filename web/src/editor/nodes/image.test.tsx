import "@testing-library/jest-dom/vitest";
import { MarkdownManager } from "@tiptap/markdown";
import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ApiError } from "../../data/request";
import { I18nProvider } from "../../i18n";
import { blockExtensions } from "../extensions";
import { PageContext } from "./generated";
import { AttachmentImage, insertAttachment } from "./image";

const uploads: Array<{ onProgress?: (loaded: number, total: number) => void; resolve: (v: unknown) => void; reject: (e: unknown) => void }> = [];

vi.mock("../../data/attachments", () => ({
  uploadAttachment: (_page: string, _file: File, onProgress?: (loaded: number, total: number) => void) =>
    new Promise((resolve, reject) => uploads.push({ onProgress, resolve, reject })),
  useAttachmentLink: (_page: string, name: string | null) =>
    name === "sumiu.jpg"
      ? { isError: true, error: new ApiError(404, { error: "not_found", message: "" }) }
      : { isError: false, data: name ? { src: `/raw/${name}` } : undefined },
}));

const extensions = [AttachmentImage, ...blockExtensions];
const md = new MarkdownManager({ extensions });

async function renderPage(markdown: string) {
  let editor: Editor | null = null;
  function Page() {
    const created = useEditor({ extensions, content: md.parse(markdown), onCreate: ({ editor: e }) => (editor = e as Editor) });
    return <EditorContent editor={created} />;
  }
  render(
    <I18nProvider>
      <PageContext.Provider value={{ kbId: "kb-1", nodeId: "vistoria" }}>
        <Page />
      </PageContext.Provider>
    </I18nProvider>,
  );
  await waitFor(() => expect(editor).not.toBeNull());
  return () => editor!;
}

describe("AttachmentImage", () => {
  beforeEach(() => {
    uploads.length = 0;
  });

  it.each(["![Fachada](arquivos/fachada.jpg)", "![](arquivos/planta-2.png)"])("reads %j as the block and writes it back", (markdown) => {
    const doc = md.parse(markdown);
    expect(doc.content?.[0]?.type).toBe("attachmentImage");
    expect(md.serialize(doc)).toBe(markdown);
  });

  it.each(["![x](https://a.b/c.png)", "Veja ![Fachada](arquivos/fachada.jpg) aqui", "![x](arquivos/a/b.png)"])(
    "leaves %j as it was",
    (markdown) => {
      const doc = md.parse(markdown);
      expect(doc.content?.[0]?.type).toBe("paragraph");
      expect(md.serialize(doc)).toBe(markdown);
    },
  );

  it("writes a created block, and nothing before it has a file", () => {
    const block = (attrs: object) => ({ type: "doc", content: [{ type: "attachmentImage", attrs }] });
    expect(md.serialize(block({ src: "arquivos/foto.jpg", caption: "Telhado" }))).toBe("![Telhado](arquivos/foto.jpg)");
    expect(md.serialize(block({ progress: 0.5 }))).toBe("");
  });

  it("shows the image with its caption, and a missing attachment as missing", async () => {
    await renderPage("![Fachada](arquivos/fachada.jpg)\n\n![Sumiu](arquivos/sumiu.jpg)");
    expect(await screen.findByRole("img", { name: "Fachada" })).toHaveAttribute("src", "/raw/fachada.jpg");
    expect(screen.getByRole("img", { name: "Fachada" })).toHaveAttribute("loading", "lazy");
    expect(screen.getByDisplayValue("Fachada")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Arquivo não encontrado");
  });

  it("uploads a pasted image with its progress, then shows it", async () => {
    const editor = await renderPage("");
    await act(async () => insertAttachment(editor(), [new File(["x"], "foto.jpg", { type: "image/jpeg" })], "vistoria"));
    await act(async () => uploads[0]!.onProgress?.(1, 4));
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "25");
    expect(md.serialize(editor().getJSON()).trim()).toBe("");

    await act(async () => uploads[0]!.resolve({ name: "foto.jpg" }));
    expect(document.querySelector("img")).toHaveAttribute("src", "/raw/foto.jpg");
    expect(md.serialize(editor().getJSON()).trim()).toBe("![](arquivos/foto.jpg)");
  });

  it("shows an upload over the limit with Tentar de novo, which sends it again", async () => {
    const editor = await renderPage("");
    await act(async () => insertAttachment(editor(), [new File(["x"], "grande.jpg", { type: "image/jpeg" })], "vistoria"));
    await act(async () => uploads[0]!.reject(new ApiError(413, { error: "attachment_too_large", message: "" })));
    expect(screen.getByRole("alert")).toHaveTextContent("Arquivo maior que 100 MB");

    await act(async () => screen.getByRole("button", { name: "Tentar de novo" }).click());
    expect(screen.getByRole("button", { name: "Enviar" })).toBeInTheDocument();
    const input = screen.getByLabelText("Envie uma imagem") as HTMLInputElement;
    await act(async () => fireEvent.change(input, { target: { files: [new File(["x"], "menor.jpg", { type: "image/jpeg" })] } }));
    await act(async () => uploads[1]!.reject(new ApiError(0, null)));
    expect(screen.getByRole("alert")).toHaveTextContent(/conexão/);

    await act(async () => screen.getByRole("button", { name: "Tentar de novo" }).click());
    expect(uploads).toHaveLength(3);
  });
});
