import "@testing-library/jest-dom/vitest";
import type { JSONContent } from "@tiptap/core";
import { MarkdownManager } from "@tiptap/markdown";
import { EditorContent, useEditor } from "@tiptap/react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { I18nProvider } from "../../i18n";
import { blockExtensions } from "../extensions";
import { BlockMath } from "./blockMath";
import { InlineMath } from "./math";

const extensions = [BlockMath, InlineMath, ...blockExtensions];
const md = new MarkdownManager({ extensions });

const types = (doc: JSONContent): string[] => (doc.content ?? []).flatMap((node) => [node.type!, ...types(node)]);

describe("BlockMath", () => {
  it("reads $$ lines as a formula block and writes them back as they were", () => {
    const markdown = "Prêmio:\n\n$$\nP = V \\times t\n$$\n\nCom $x$ na linha.";
    const doc = md.parse(markdown);
    expect(doc.content?.[1]).toEqual({ type: "blockMath", attrs: { tex: "P = V \\times t" } });
    expect(types(doc)).toContain("inlineMath");
    expect(md.serialize(doc)).toBe(markdown);
  });

  it("writes a created formula block on three lines", () => {
    const doc = { type: "doc", content: [{ type: "blockMath", attrs: { tex: "\\pi r^2" } }] };
    expect(md.serialize(doc)).toBe("$$\n\\pi r^2\n$$");
  });

  it("renders the formula, and an invalid one as its source with the error", async () => {
    function Page() {
      const editor = useEditor({ extensions, content: md.parse("$$\nx^2\n$$\n\n$$\n\\frac{1\n$$") });
      return <EditorContent editor={editor} />;
    }
    const { container } = render(
      <I18nProvider>
        <Page />
      </I18nProvider>,
    );

    await waitFor(() => expect(container.querySelector(".katex-display")).toBeInTheDocument());
    const invalid = screen.getByText("$$ \\frac{1 $$", { normalizer: (text) => text.replace(/\s+/g, " ") });
    expect(invalid).toHaveClass("text-err", "font-mono");

    fireEvent.click(invalid);
    expect(screen.getByRole("textbox", { name: "Fonte da fórmula" })).toHaveValue("\\frac{1");
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
