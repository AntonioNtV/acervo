import { getSchema, type JSONContent } from "@tiptap/core";
import { MarkdownManager } from "@tiptap/markdown";
import { blockExtensions } from "../extensions";

const extensions = blockExtensions;
const manager = new MarkdownManager({ extensions });
const schema = getSchema(extensions);

const form = (open: boolean, heading: string) =>
  `<details${open ? " open" : ""}>\n<summary>\n\n${heading}\n\n</summary>\n\nAs **apólices** do ramo.\n\n- RG\n- CNH\n\n</details>`;

describe("ToggleHeading", () => {
  it.each([
    [true, "# Documentos"],
    [false, "## Documentos"],
    [true, "### Documentos"],
    [false, "### Documentos"],
    // A heading 4–6 typed into its heading with `####` must reopen too.
    [true, "###### Documentos"],
  ])("open=%s %s reads as the node and writes back byte for byte", (open, heading) => {
    const markdown = form(open, heading);
    const doc = manager.parse(markdown);
    const [node] = doc.content ?? [];
    expect(node?.type).toBe("toggleHeading");
    expect(node?.attrs?.open).toBe(open);
    expect(node?.content?.[0]).toMatchObject({ type: "heading", attrs: { level: heading.indexOf(" ") } });
    expect(manager.serialize(doc)).toBe(markdown);
  });

  it("leaves a toggle with a one-line summary to Toggle", () => {
    const doc = manager.parse("<details>\n<summary>## Não é título</summary>\n\nTexto.\n\n</details>");
    expect(doc.content?.[0]?.type).toBe("details");
  });

  it("writes a created one, and collapsing it drops open", () => {
    const created: JSONContent = {
      type: "doc",
      content: [
        {
          type: "toggleHeading",
          content: [
            { type: "heading", attrs: { level: 2 }, content: [{ type: "text", text: "Prazos" }] },
            { type: "paragraph", content: [{ type: "text", text: "Trinta dias." }] },
          ],
        },
      ],
    };
    const node = schema.nodeFromJSON(created);
    expect(manager.serialize(node.toJSON())).toBe(
      "<details open>\n<summary>\n\n## Prazos\n\n</summary>\n\nTrinta dias.\n\n</details>",
    );

    const collapsed = node.copy(node.content.replaceChild(0, node.child(0).type.create({ open: false }, node.child(0).content)));
    expect(manager.serialize(collapsed.toJSON())).toBe(
      "<details>\n<summary>\n\n## Prazos\n\n</summary>\n\nTrinta dias.\n\n</details>",
    );
  });
});
