import { Node, type Editor } from "@tiptap/core";
import type { Node as PmNode } from "@tiptap/pm/model";
import { NodeViewWrapper, ReactNodeViewRenderer, useEditorState, type ReactNodeViewProps } from "@tiptap/react";
import { createContext, useContext, useEffect, useState } from "react";
import { useI18n } from "../../i18n";
import { Breadcrumb } from "../../screens/shell/Breadcrumb";
import type { BlockKind } from "../blocks";
import { startBefore } from "../tokenize";
import "./generated.css";


/** A block drawn from the page, never typed into: `comment` alone on its line, and nothing else, is the block. */
function generatedBlock(name: string, comment: string) {
  const line = new RegExp(`^${comment}(?:\\n|$)`);
  return Node.create({
    name,
    group: "block",
    atom: true,
    selectable: true,
    draggable: true,
    parseHTML: () => [{ tag: `div[data-${name}]` }],
    renderHTML: () => ["div", { [`data-${name}`]: "" }],
    markdownTokenizer: {
      name,
      level: "block",
      start: startBefore(new RegExp(`^${comment}$`, "m")),
      tokenize: (src) => {
        const match = line.exec(src);
        return match ? { type: name, raw: match[0] } : undefined;
      },
    },
    parseMarkdown: (_token, h) => h.createNode(name),
    renderMarkdown: () => comment,
  });
}

type Heading = { pos: number; level: number; text: string };

function headingsOf(doc: PmNode): Heading[] {
  const found: Heading[] = [];
  doc.descendants((node, pos) => {
    const level = Number(node.attrs.level);
    if (node.type.name === "heading" && (level === 2 || level === 3)) found.push({ pos, level, text: node.textContent });
  });
  return found;
}

const domOf = (editor: Editor, heading: Heading) => editor.view.nodeDOM(heading.pos) as HTMLElement | null;

export function TableOfContentsView({ editor }: ReactNodeViewProps) {
  const { t } = useI18n();
  const headings = useEditorState({ editor, selector: ({ editor: current }) => headingsOf(current.state.doc) });
  const [active, setActive] = useState(-1);

  // The section on screen is the last one whose heading has passed the top third of the window.
  useEffect(() => {
    const spot = () =>
      setActive(
        headings.reduce(
          (last, heading, index) => ((domOf(editor, heading)?.getBoundingClientRect().top ?? Infinity) <= innerHeight / 3 ? index : last),
          -1,
        ),
      );
    spot();
    window.addEventListener("scroll", spot, { capture: true, passive: true });
    return () => window.removeEventListener("scroll", spot, { capture: true });
  }, [editor, headings]);

  return (
    <NodeViewWrapper as="nav" className="toc" aria-label={t("editor.block.toc")} contentEditable={false}>
      {headings.length ? (
        headings.map((heading, index) => (
          <button
            key={heading.pos}
            type="button"
            className={heading.level === 3 ? "toc-link toc-h3" : "toc-link"}
            aria-current={index === active ? "location" : undefined}
            onClick={() => domOf(editor, heading)?.scrollIntoView({ block: "start", behavior: "smooth" })}
          >
            {heading.text}
          </button>
        ))
      ) : (
        <p className="toc-empty">{t("editor.toc.empty")}</p>
      )}
    </NodeViewWrapper>
  );
}

/** The page the editor is on, for the blocks that show where it sits: `PageView` provides it. */
export const PageContext = createContext<{ kbId: string; nodeId: string } | null>(null);

export function BreadcrumbView() {
  const page = useContext(PageContext);
  return (
    <NodeViewWrapper className="breadcrumb-block" contentEditable={false}>
      {page && <Breadcrumb kbId={page.kbId} nodeId={page.nodeId} />}
    </NodeViewWrapper>
  );
}

/** `<!-- toc -->`: the page's `##` and `###` headings, each leading to its section. */
export const TableOfContents = generatedBlock("tableOfContents", "<!-- toc -->").extend({
  addNodeView: () => ReactNodeViewRenderer(TableOfContentsView),
});

/** `<!-- acervo:breadcrumb -->`: the path to this page, the top bar's, so it follows a move. */
export const BreadcrumbBlock = generatedBlock("breadcrumb", "<!-- acervo:breadcrumb -->").extend({
  addNodeView: () => ReactNodeViewRenderer(BreadcrumbView),
});

/** After `RawInline` and `RawBlock`, which would keep the comments raw: marked tries the last registered first. */
export const generatedExtensions = [TableOfContents, BreadcrumbBlock];

/** For the "/" menu: inserted with `insertContent({ type: "tableOfContents" })` and `{ type: "breadcrumb" }`. */
export const GENERATED_KINDS = [
  { id: "toc", group: "blocks" },
  { id: "breadcrumb", group: "blocks" },
] satisfies BlockKind[];
