import { getSchema } from "@tiptap/core";
import { blockExtensions } from "./extensions";
import { bindSource, parseMarkdown, serializeMarkdown, type Source } from "./markdown";

const fixtures = import.meta.glob<string>("./fixtures/*.md", { eager: true, query: "?raw", import: "default" });
const schema = getSchema(blockExtensions);
const NO_SOURCE: Source = { lead: "", chunks: [], nodes: [] };

function open(markdown: string) {
  const { doc, source } = parseMarkdown(markdown);
  const node = schema.nodeFromJSON(doc);
  return { node, source: bindSource(source, node) };
}

/** Every block written again by its own serializer, as if the person had edited all of them. */
const rewrite = (markdown: string) => serializeMarkdown(open(markdown).node, NO_SOURCE);

// Written in the canonical style, so even a rewrite gives back the same bytes.
const canonical = ["blocks.md", "links.md", "unknown-html.md"];

const raws = (markdown: string) => markdown.match(/<!--[\s\S]*?-->|<\/?[a-z][^>]*>|\[\^[^\]]+\]:?[^\n]*/gi) ?? [];

describe("Markdown round-trip", () => {
  it.each(Object.entries(fixtures))("%s opened and left untouched is the same text", (_name, markdown) => {
    const { node, source } = open(markdown);
    expect(serializeMarkdown(node, source)).toBe(markdown);
  });

  it.each(Object.entries(fixtures))("%s rewritten block by block reads back the same", (name, markdown) => {
    const rewritten = rewrite(markdown);
    if (canonical.some((file) => name.endsWith(file))) expect(rewritten).toBe(markdown);
    // The documented normalization: same blocks, raw constructs (HTML, comments, footnotes) byte for byte.
    expect(open(rewritten).node.eq(open(markdown).node)).toBe(true);
    for (const raw of raws(markdown)) expect(rewritten).toContain(raw);
  });

  it("keeps every provenance comment of an agent's page where it was", () => {
    const markdown = fixtures["./fixtures/agent-page.md"]!;
    const { node, source } = open(markdown);
    const paragraph = schema.nodeFromJSON({ type: "paragraph", content: [{ type: "text", text: "Só o boleto." }] });
    const edited = node.copy(node.content.replaceChild(1, paragraph));
    const out = serializeMarkdown(edited, source);
    expect(out).toContain("## Documentos\n\nSó o boleto.\n\n<!-- origem: Condições Gerais 2026.pdf p. 14 -->");
    expect(out.slice(out.indexOf("## Prazos"))).toBe(markdown.slice(markdown.indexOf("## Prazos")));
  });

  it("reads [[links]] as page links and writes them back as typed", () => {
    const { node } = open("Ver [[Renovação]] e `[[não]]`.\n");
    const links: string[] = [];
    node.descendants((child) => {
      if (child.type.name === "pageLink") links.push(child.attrs.title);
    });
    expect(links).toEqual(["Renovação"]);
    expect(serializeMarkdown(node, NO_SOURCE)).toBe("Ver [[Renovação]] e `[[não]]`.\n");
  });

  it("keeps an image in a paragraph that was edited", () => {
    const { node, source } = open("Planta: ![planta](img/planta.png) do térreo.\n");
    const paragraph = node.child(0);
    const longer = paragraph.copy(paragraph.content.addToEnd(schema.text(" Nova.")));
    const edited = node.copy(node.content.replaceChild(0, longer));
    expect(serializeMarkdown(edited, source)).toBe("Planta: ![planta](img/planta.png) do térreo. Nova.\n");
  });

  it("keeps an escaped list marker a paragraph after an edit", () => {
    const { node, source } = open("1\\. não é lista\n\n\\- nem isto\n");
    const edited = node.copy(
      node.content.replaceChild(0, schema.nodeFromJSON({ type: "paragraph", content: [{ type: "text", text: "1. ainda não" }] })),
    );
    const out = serializeMarkdown(edited, source);
    expect(out).toBe("1\\. ainda não\n\n\\- nem isto\n");
    expect(open(out).node.eq(edited)).toBe(true);
  });

  it("serializes a long page in linear time", () => {
    /** The page of `n` paragraphs as opened, built directly: parsing it is not what is timed. */
    const page = (n: number) => {
      const json = Array.from({ length: n }, (_, i) => ({ type: "paragraph", content: [{ type: "text", text: `Item ${i}` }] }));
      const chunks = json.map((block, i) => ({ body: `Item ${i}`, gap: i === n - 1 ? "\n" : "\n\n", json: [block] }));
      const node = schema.nodeFromJSON({ type: "doc", content: json });
      const novo = schema.nodeFromJSON({ type: "paragraph", content: [{ type: "text", text: "Novo" }] });
      const edited = node.copy(node.content.replaceChild(0, novo));
      return { edited, source: bindSource({ lead: "", chunks, nodes: [] }, node) };
    };
    const fastest = (n: number) => {
      const { edited, source } = page(n);
      let best = Infinity;
      for (let run = 0; run < 3; run++) {
        const start = performance.now();
        serializeMarkdown(edited, source);
        best = Math.min(best, performance.now() - start);
      }
      return best;
    };
    fastest(1_000);
    // Ten times the blocks: about ten times the time when linear, a hundred when quadratic.
    expect(fastest(10_000)).toBeLessThan(fastest(1_000) * 30);
  });

  it("normalizes only line endings of a page nobody edited", () => {
    const { node, source } = open("## A\r\n\r\nTexto\r\n");
    expect(serializeMarkdown(node, source)).toBe("## A\n\nTexto\n");
  });
});
