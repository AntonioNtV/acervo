import { Node } from "@tiptap/core";
import { NodeViewWrapper, ReactNodeViewRenderer, type ReactNodeViewProps } from "@tiptap/react";
import { useEffect, useState } from "react";
import { FormulaEditor } from "../../ui/FormulaEditor";
import type { BlockKind } from "../blocks";
import "./math.css";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    inlineMath: { insertInlineMath: () => ReturnType };
  }
}

type Katex = typeof import("katex").default;

let loading: Promise<Katex> | null = null;
// Only a page with a formula pays for KaTeX: it stays out of the main bundle.
const loadKatex = () =>
  (loading ??= Promise.all([import("katex"), import("katex/dist/katex.min.css")]).then(([katex]) => katex.default));

function useKatex(): Katex | null {
  const [katex, setKatex] = useState<Katex | null>(null);
  useEffect(() => {
    let live = true;
    void loadKatex().then((loaded) => live && setKatex(() => loaded));
    return () => {
      live = false;
    };
  }, []);
  return katex;
}

function render(katex: Katex, tex: string): { html: string } | { error: string } {
  try {
    return { html: katex.renderToString(tex, { throwOnError: true }) };
  } catch (error) {
    return { error: error instanceof katex.ParseError ? error.rawMessage : String(error) };
  }
}

/** Opens on `$` before a non-space, closes on `$` after a non-space and not before a digit: `R$ 400` stays text. */
const INLINE_MATH = /^\$(?=\S)((?:\\.|[^\\$\n])+)(?<=\S)\$(?!\d)/;

export function InlineMathView({ node, updateAttributes, deleteNode }: ReactNodeViewProps) {
  const tex = String(node.attrs.tex);
  const katex = useKatex();
  // A new formula has no source yet: it opens with its editor.
  const [editing, setEditing] = useState<string | null>(tex ? null : "");
  const shown = katex ? render(katex, tex) : null;
  const draft = katex && editing ? render(katex, editing) : null;
  const close = (source: string) => {
    setEditing(null);
    if (!source.trim()) deleteNode();
    else if (source !== tex) updateAttributes({ tex: source });
  };
  return (
    <NodeViewWrapper as="span" className="inline-math">
      <button type="button" className="inline-math-source" contentEditable={false} onClick={() => setEditing(tex)}>
        {shown && "html" in shown ? (
          <span dangerouslySetInnerHTML={{ __html: shown.html }} />
        ) : (
          <span className={shown ? "font-mono text-err" : "font-mono"}>{`$${tex}$`}</span>
        )}
      </button>
      {editing !== null && (
        <span className="inline-math-panel" contentEditable={false}>
          <FormulaEditor
            kind="tex"
            source={editing}
            error={draft && "error" in draft ? draft.error : undefined}
            onChange={setEditing}
            onClose={() => close(editing)}
            onCancel={() => close(tex)}
          />
        </span>
      )}
    </NodeViewWrapper>
  );
}

/** `$P = V \times t$`: a formula inside the text, shown in math type. */
export const InlineMath = Node.create({
  name: "inlineMath",
  group: "inline",
  inline: true,
  atom: true,
  selectable: true,
  addAttributes: () => ({ tex: { default: "" } }),
  parseHTML: () => [
    { tag: "span[data-inline-math]", getAttrs: (el) => ({ tex: (el as HTMLElement).dataset.inlineMath ?? "" }) },
  ],
  renderHTML: ({ node }) => ["span", { "data-inline-math": node.attrs.tex }, `$${node.attrs.tex}$`],
  renderText: ({ node }) => `$${node.attrs.tex}$`,
  addCommands() {
    return {
      insertInlineMath:
        () =>
        ({ commands }) =>
          commands.insertContent({ type: this.name }),
    };
  },
  addNodeView: () => ReactNodeViewRenderer(InlineMathView),
  markdownTokenizer: {
    name: "inlineMath",
    level: "inline",
    start: (src) => src.indexOf("$"),
    tokenize: (src) => {
      const match = INLINE_MATH.exec(src);
      return match ? { type: "inlineMath", raw: match[0], text: match[1] } : undefined;
    },
  },
  parseMarkdown: (token, h) => h.createNode("inlineMath", { tex: token.text }),
  renderMarkdown: (node) => `$${node.attrs?.tex ?? ""}$`,
});

/** For the "/" menu: `insertInlineMath()` puts an empty formula at the cursor with its editor open. */
export const MATH_KINDS = [{ id: "inlineEquation", group: "blocks" }] satisfies BlockKind[];
