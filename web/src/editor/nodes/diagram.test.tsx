import "@testing-library/jest-dom/vitest";
import { MarkdownManager } from "@tiptap/markdown";
import { EditorContent, useEditor } from "@tiptap/react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { I18nProvider } from "../../i18n";
import { blockExtensions } from "../extensions";
import { Diagram } from "./diagram";

const mermaid = vi.hoisted(() => ({
  initialize: vi.fn(),
  render: vi.fn(async (_id: string, source: string) => {
    if (source.includes("-->|")) throw new Error("Parse error on line 2");
    return { svg: `<svg data-testid="drawing"><text>${source.split("\n")[0]}</text></svg>` };
  }),
}));
vi.mock("mermaid", () => ({ default: mermaid }));

const extensions = [Diagram, ...blockExtensions];
const md = new MarkdownManager({ extensions });

const FLOW = "```mermaid\nflowchart LR\n  A[Proposta] --> B[Emitir]\n```";

function Page({ markdown }: { markdown: string }) {
  const editor = useEditor({ extensions, content: md.parse(markdown) });
  return <EditorContent editor={editor} />;
}

const renderPage = (markdown: string) =>
  render(
    <I18nProvider>
      <Page markdown={markdown} />
    </I18nProvider>,
  );

describe("Diagram", () => {
  it("reads a mermaid fence as a diagram and writes it back as it was", () => {
    const markdown = `Fluxo:\n\n${FLOW}\n\n\`\`\`mermaid\n\`\`\``;
    const doc = md.parse(markdown);
    expect(doc.content?.[1]).toEqual({ type: "diagram", content: [{ type: "text", text: "flowchart LR\n  A[Proposta] --> B[Emitir]" }] });
    expect(doc.content?.[2]).toEqual({ type: "diagram", content: [] });
    expect(md.serialize(doc)).toBe(markdown);
  });

  it("writes a created diagram as a mermaid fence", () => {
    const doc = { type: "doc", content: [{ type: "diagram", content: [{ type: "text", text: "sequenceDiagram\n  A->>B: Oi" }] }] };
    expect(md.serialize(doc)).toBe("```mermaid\nsequenceDiagram\n  A->>B: Oi\n```");
  });

  it("leaves other code blocks as code blocks", () => {
    const markdown = "```ts\nconst a = 1;\n```\n\n```\nflowchart LR\n```";
    const doc = md.parse(markdown);
    expect(doc.content?.map((node) => node.type)).toEqual(["codeBlock", "codeBlock"]);
    expect(md.serialize(doc)).toBe(markdown);
  });

  it("draws the source strictly, and shows it as written under Editar", async () => {
    const { container } = renderPage(FLOW);

    expect(await screen.findByTestId("drawing")).toBeInTheDocument();
    expect(mermaid.initialize).toHaveBeenCalledWith(expect.objectContaining({ securityLevel: "strict" }));
    expect(container.querySelector("pre.diagram-code")).not.toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Editar" }));
    expect(container.querySelector("pre.diagram-code")).toBeVisible();
    expect(container.querySelector("pre.diagram-code")).toHaveTextContent("A[Proposta] --> B[Emitir]");
    expect(screen.queryByTestId("drawing")).not.toBeInTheDocument();
  });

  it("shows an invalid source as written, with the error", async () => {
    const { container } = renderPage("```mermaid\nflowchart LR\n  A -->| B\n```");

    expect(await screen.findByRole("alert")).toHaveTextContent("Parse error on line 2");
    expect(screen.getByRole("alert")).toHaveClass("text-err");
    await waitFor(() => expect(container.querySelector("pre.diagram-code")).toBeVisible());
    expect(container.querySelector("pre.diagram-code")).toHaveTextContent("A -->| B");
  });
});
