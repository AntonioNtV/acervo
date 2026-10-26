import { attachmentName } from "./attachment";

describe("attachmentName", () => {
  it.each([
    ["arquivos/foto.jpg", "foto.jpg"],
    ["arquivos/relatório-2.pdf", "relatório-2.pdf"],
    ["arquivos/", null],
    ["arquivos/a/b.jpg", null],
    ["./arquivos/foto.jpg", null],
    ["https://a.b/arquivos/foto.jpg", null],
    ["foto.jpg", null],
  ])("%s → %s", (href, name) => {
    expect(attachmentName(href)).toBe(name);
  });
});
