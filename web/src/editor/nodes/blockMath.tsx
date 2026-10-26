import { Node } from "@tiptap/core";
import { NodeViewWrapper, ReactNodeViewRenderer, type ReactNodeViewProps } from "@tiptap/react";
import { useEffect, useState } from "react";
import { FormulaEditor } from "../../ui/FormulaEditor";
import type { BlockKind } from "../blocks";
import { startBefore } from "../tokenize";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    blockMath: { insertBlockMath: () => ReturnType };
  }
}

type Katex = typeof import("katex").default;

// The same dynamic imports as `math.tsx`: one KaTeX chunk, fetched once, only by a page with a formula.
// shortcut: a second copy of math.tsx's loader, its file is not this card's; export it from there when one is free.
let loading: Promise<Katex> | null = null;
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
    return { html: katex.renderToString(tex, { displayMode: true, throwOnError: true }) };
  } catch (error) {
    return { error: error instanceof katex.ParseError ? error.rawMessage : String(error) };
  }
}

/** `$$`, the TeX, `$$`, each on its own line. */
const BLOCK_MATH = /^\$\$\n([\s\S]*?)\n\$\$(?:\n|$)/;

const markdownOf = (tex: unknown) => `$$\n${tex ?? ""}\n$$`;

export function BlockMathView({ editor, node, getPos, updateAttributes, deleteNode }: ReactNodeViewProps) {
  const tex = String(node.attrs.tex);
  const katex = useKatex();
  // A new formula has no source yet: it opens with its editor.
  const [editing, setEditing] = useState<string | null>(tex ? null : "");
  const shown = katex ? render(katex, tex) : null;
  const draft = katex && editing ? render(katex, editing) : null;
  const close = (next: string) => {
    setEditing(null);
    const pos = getPos();
    if (!next.trim()) deleteNode();
    else if (next !== tex) updateAttributes({ tex: next });
    // The panel's input is inside the editor: focus the view itself, then put the caret after the block.
    if (pos !== undefined) {
      editor.view.focus();
      editor.commands.setTextSelection(next.trim() ? pos + node.nodeSize : pos);
    }
  };
  return (
    <NodeViewWrapper className="relative my-1" contentEditable={false}>
      <button
        type="button"
        className="block w-full cursor-pointer rounded-[6px] border-0 bg-transparent px-0 py-2 text-center text-text hover:bg-subtle"
        // The editor would take the focus back on mousedown; the panel's input gets it.
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => setEditing(tex)}
      >
        {shown && "html" in shown ? (
          <span dangerouslySetInnerHTML={{ __html: shown.html }} />
        ) : (
          <>
            <span className={shown ? "block whitespace-pre-wrap font-mono text-13 text-err" : "block whitespace-pre-wrap font-mono text-13"}>
              {markdownOf(tex)}
            </span>
            {shown && <span className="block text-12 text-err">{shown.error}</span>}
          </>
        )}
      </button>
      {editing !== null && (
        <div className="absolute top-[calc(100%+4px)] left-1/2 z-20 max-w-full -translate-x-1/2">
          <FormulaEditor
            kind="tex"
            source={editing}
            error={draft && "error" in draft ? draft.error : undefined}
            onChange={setEditing}
            onClose={() => close(editing)}
            onCancel={() => close(tex)}
          />
        </div>
      )}
    </NodeViewWrapper>
  );
}

/** `$$ … $$` on lines of their own: a formula as a block of its own, centered. */
export const BlockMath = Node.create({
  name: "blockMath",
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,
  addAttributes: () => ({ tex: { default: "" } }),
  parseHTML: () => [{ tag: "div[data-block-math]", getAttrs: (el) => ({ tex: (el as HTMLElement).dataset.blockMath ?? "" }) }],
  renderHTML: ({ node }) => ["div", { "data-block-math": node.attrs.tex }, markdownOf(node.attrs.tex)],
  renderText: ({ node }) => markdownOf(node.attrs.tex),
  addCommands() {
    return {
      insertBlockMath:
        () =>
        ({ commands }) =>
          commands.insertContent({ type: this.name }),
    };
  },
  addNodeView: () => ReactNodeViewRenderer(BlockMathView),
  markdownTokenizer: {
    name: "blockMath",
    level: "block",
    start: startBefore(/^\$\$$/m),
    tokenize: (src) => {
      const match = BLOCK_MATH.exec(src);
      return match ? { type: "blockMath", raw: match[0], text: match[1] } : undefined;
    },
  },
  parseMarkdown: (token, h) => h.createNode("blockMath", { tex: token.text }),
  renderMarkdown: (node) => markdownOf(node.attrs?.tex),
});

/** For the "/" menu: `insertBlockMath()` puts an empty formula block with its editor open. */
export const blockMathKinds: BlockKind[] = [{ id: "equation", group: "blocks" }];
