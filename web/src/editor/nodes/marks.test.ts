import { getSchema, type JSONContent } from "@tiptap/core";
import { MarkdownManager } from "@tiptap/markdown";
import { blockExtensions } from "../extensions";
import { markExtensions } from "./marks";

const extensions = [...blockExtensions, ...markExtensions];
const md = new MarkdownManager({ extensions });
const schema = getSchema(extensions);

const marksOf = (markdown: string) => {
  const names: string[] = [];
  schema.nodeFromJSON(md.parse(markdown)).descendants((node) => {
    node.marks.forEach((mark) => names.push(mark.attrs.color ? `${mark.type.name}:${mark.attrs.color}` : mark.type.name));
  });
  return names;
};
const roundTrip = (markdown: string) => md.serialize(md.parse(markdown)).trim();

describe("text marks", () => {
  it.each([
    ["<u>a</u>", "underline"],
    ["==a==", "highlight"],
    ['<span data-color="red">a</span>', "textColor:red"],
  ])("%s parses to its mark and writes back identical", (markdown, mark) => {
    expect(marksOf(`Ver ${markdown} aqui.`)).toEqual([mark]);
    expect(roundTrip(`Ver ${markdown} aqui.`)).toBe(`Ver ${markdown} aqui.`);
  });

  it.each(["a == b", '<span data-color="violet">a</span>'])("%s stays as written", (markdown) => {
    expect(marksOf(markdown)).toEqual([]);
    expect(roundTrip(markdown)).toBe(markdown);
  });

  it("writes created marks in the canonical form", () => {
    const text = (marks: JSONContent["marks"]) => ({ type: "text", text: "a", marks });
    const doc = {
      type: "doc",
      content: [
        {
          type: "paragraph",
          content: [
            text([{ type: "underline" }]),
            { type: "text", text: " " },
            text([{ type: "highlight" }]),
            { type: "text", text: " " },
            text([{ type: "textColor", attrs: { color: "blue" } }]),
          ],
        },
      ],
    };
    expect(md.serialize(doc).trim()).toBe('<u>a</u> ==a== <span data-color="blue">a</span>');
  });
});
