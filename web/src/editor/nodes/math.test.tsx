import "@testing-library/jest-dom/vitest";
import type { JSONContent } from "@tiptap/core";
import { MarkdownManager } from "@tiptap/markdown";
import { EditorContent, useEditor } from "@tiptap/react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { I18nProvider } from "../../i18n";
import { blockExtensions } from "../extensions";
import { InlineMath } from "./math";

const md = new MarkdownManager({ extensions: [InlineMath, ...blockExtensions] });

const formulas = (doc: JSONContent): string[] =>
  (doc.content ?? []).flatMap((node) => (node.type === "inlineMath" ? [String(node.attrs?.tex)] : formulas(node)));

describe("InlineMath", () => {
  it.each([
    ["O prêmio é $P = V \\times t$, com taxa.", ["P = V \\times t"]],
    ["$x$ e $y^2$", ["x", "y^2"]],
    ["R$ 400 e R$ 500", []],
    ["custa $5 ou $6", []],
    ["US$100", []],
    ["de $a $ b", []],
    ["de $a$5", []],
    ["uma $linha\nquebrada$", []],
    ["preço \\$x$", []],
    ["$a \\$ b$", ["a \\$ b"]],
    ["código `$x$` aqui", []],
  ])("reads %j", (markdown, expected) => {
    expect(formulas(md.parse(markdown))).toEqual(expected);
  });

  it.each([
    "O prêmio é $P = V \\times t$, com taxa.",
    "R$ 400 e R$ 500",
    "custa $5 ou $6",
    "US$100",
  ])("writes %j back as it was", (markdown) => {
    expect(md.serialize(md.parse(markdown))).toBe(markdown);
  });

  it("writes a created formula between dollars", () => {
    const doc = {
      type: "doc",
      content: [
        {
          type: "paragraph",
          content: [{ type: "text", text: "Área " }, { type: "inlineMath", attrs: { tex: "\\pi r^2" } }],
        },
      ],
    };
    expect(md.serialize(doc)).toBe("Área $\\pi r^2$");
  });

  it("renders math, and the source of an invalid formula as an error", async () => {
    function Page() {
      const content = md.parse("$x^2$ e $\\frac{1$");
      const editor = useEditor({ extensions: [InlineMath, ...blockExtensions], content });
      return <EditorContent editor={editor} />;
    }
    const { container } = render(
      <I18nProvider>
        <Page />
      </I18nProvider>,
    );

    await waitFor(() => expect(container.querySelector(".katex")).toBeInTheDocument());
    const invalid = screen.getByText("$\\frac{1$");
    expect(invalid).toHaveClass("text-err", "font-mono");

    fireEvent.click(invalid);
    expect(screen.getByRole("textbox", { name: "Fonte da fórmula" })).toHaveValue("\\frac{1");
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
