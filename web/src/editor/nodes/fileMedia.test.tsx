import type { JSONContent } from "@tiptap/core";
import { MarkdownManager } from "@tiptap/markdown";
import { blockExtensions } from "../extensions";
import { AttachmentFile, mediaKind } from "./fileMedia";

const md = new MarkdownManager({ extensions: [AttachmentFile, ...blockExtensions] });

const types = (doc: JSONContent) => (doc.content ?? []).map((node) => node.type);

describe("AttachmentFile", () => {
  it.each(["[contrato.pdf](arquivos/contrato.pdf)", "[vistoria.mp4](arquivos/vistoria.mp4)", "[ligacao.m4a](arquivos/ligacao.m4a)"])(
    "reads %j alone in a paragraph as the block and writes it back byte for byte",
    (markdown) => {
      const page = `# Sinistro\n\n${markdown}\n\nTexto.`;
      const doc = md.parse(page);
      expect(types(doc)).toEqual(["heading", "attachmentFile", "paragraph"]);
      expect(md.serialize(doc)).toBe(page);
    },
  );

  it("keeps the label it was written with", () => {
    const doc = md.parse("[Contrato assinado](arquivos/contrato.pdf)");
    expect(doc.content?.[0]?.attrs).toMatchObject({ src: "arquivos/contrato.pdf", label: "Contrato assinado" });
    expect(md.serialize(doc)).toBe("[Contrato assinado](arquivos/contrato.pdf)");
  });

  it("writes an uploaded block with the attachment's name, and nothing while it uploads", () => {
    const block = (src: string | null) => ({ type: "doc", content: [{ type: "attachmentFile", attrs: { src } }] });
    expect(md.serialize(block("arquivos/vistoria-2.mp4"))).toBe("[vistoria-2.mp4](arquivos/vistoria-2.mp4)");
    expect(md.serialize(block(null))).toBe("");
  });

  it.each([
    "[site](https://x.y)",
    "Veja [contrato.pdf](arquivos/contrato.pdf) antes.",
    "[contrato.pdf](arquivos/contrato.pdf)\ncom uma linha depois",
    "antes\n[contrato.pdf](arquivos/contrato.pdf)",
    "[pasta](arquivos/a/b.pdf)",
  ])("leaves %j a link in its paragraph", (markdown) => {
    const doc = md.parse(markdown);
    expect(types(doc)).toEqual(["paragraph"]);
    expect(md.serialize(doc)).toBe(markdown);
  });

  it.each([
    ["contrato.pdf", "file"],
    ["planilha.XLSX", "file"],
    ["sem-extensao", "file"],
    ["vistoria.mp4", "video"],
    ["vistoria.webm", "video"],
    ["Vistoria.MOV", "video"],
    ["ligacao.mp3", "audio"],
    ["ligacao.m4a", "audio"],
    ["ligacao.wav", "audio"],
    ["ligacao.ogg", "audio"],
  ])("%s is a %s", (name, kind) => {
    expect(mediaKind(name)).toBe(kind);
  });
});
