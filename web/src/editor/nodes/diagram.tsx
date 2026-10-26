import { Node } from "@tiptap/core";
import { NodeViewContent, NodeViewWrapper, ReactNodeViewRenderer, type ReactNodeViewProps } from "@tiptap/react";
import { useEffect, useState, useSyncExternalStore } from "react";
import { useI18n } from "../../i18n";
import type { BlockKind } from "../blocks";
import { startBefore } from "../tokenize";
import "./diagram.css";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    diagram: { insertDiagram: () => ReturnType };
  }
}

type Mermaid = typeof import("mermaid").default;

let loading: Promise<Mermaid> | null = null;
// Only a page with a diagram pays for Mermaid: it stays out of the main bundle.
const loadMermaid = () => (loading ??= import("mermaid").then((mermaid) => mermaid.default));

const isDark = () => document.documentElement.classList.contains("dark");
// The theme provider toggles `dark` on <html>; a drawing made in one theme is redrawn in the other.
const watchTheme = (changed: () => void) => {
  const observer = new MutationObserver(changed);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
};

function themeVariables() {
  const style = getComputedStyle(document.documentElement);
  const token = (name: string) => style.getPropertyValue(name).trim();
  return {
    darkMode: isDark(),
    fontFamily: token("--font-sans"),
    fontSize: "13px",
    background: token("--bg"),
    mainBkg: token("--bg"),
    primaryColor: token("--bg"),
    primaryTextColor: token("--text"),
    primaryBorderColor: token("--text"),
    secondaryColor: token("--subtle"),
    tertiaryColor: token("--subtle"),
    nodeBorder: token("--text"),
    lineColor: token("--line-2"),
    textColor: token("--text"),
    clusterBkg: token("--subtle"),
    edgeLabelBackground: token("--bg"),
    actorBkg: token("--bg"),
    actorBorder: token("--text"),
    signalColor: token("--text"),
  };
}

let drawn = 0;

async function draw(source: string): Promise<{ svg: string } | { error: string }> {
  const mermaid = await loadMermaid();
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "strict",
    suppressErrorRendering: true,
    theme: "base",
    themeVariables: themeVariables(),
  });
  try {
    const { svg } = await mermaid.render(`diagram-${++drawn}`, source);
    return { svg };
  } catch (error) {
    return { error: error instanceof Error ? error.message : String(error) };
  }
}

// A fence of its own, ```mermaid; any other language stays a code block.
const FENCE = /^```mermaid\n(?:([\s\S]*?)\n)?```(?:\n|$)/;

const markdownOf = (source: string) => (source ? `\`\`\`mermaid\n${source}\n\`\`\`` : "```mermaid\n```");

export function DiagramView({ node }: ReactNodeViewProps) {
  const { t } = useI18n();
  const source = node.textContent;
  const dark = useSyncExternalStore(watchTheme, isDark);
  const [editing, setEditing] = useState(false);
  const [shown, setShown] = useState<{ svg: string } | { error: string } | null>(null);
  useEffect(() => {
    let live = true;
    void draw(source).then((result) => live && setShown(result));
    return () => {
      live = false;
    };
  }, [source, dark]);
  const error = shown && "error" in shown ? shown.error : null;
  // The source is the node's own text: editing it is typing in it, and an invalid one stays on screen as written.
  const raw = editing || error !== null;
  return (
    <NodeViewWrapper className="diagram">
      <div className="diagram-switch" contentEditable={false}>
        {[
          { on: !editing, label: t("editor.diagram.view") },
          { on: editing, label: t("editor.diagram.edit") },
        ].map((option, index) => (
          <button
            key={option.label}
            type="button"
            aria-pressed={option.on}
            className={option.on ? "is-on" : undefined}
            onClick={() => setEditing(index === 1)}
          >
            {option.label}
          </button>
        ))}
      </div>
      <NodeViewContent<"pre"> as="pre" className="diagram-code" hidden={!raw} />
      {!raw && shown && "svg" in shown && (
        <div className="diagram-drawing" contentEditable={false} dangerouslySetInnerHTML={{ __html: shown.svg }} />
      )}
      {error !== null && (
        <p role="alert" className="diagram-error text-12 text-err" contentEditable={false}>
          {error}
        </p>
      )}
    </NodeViewWrapper>
  );
}

const EXAMPLE = ["flowchart LR", "  A[Início] --> B{Decisão?}", "  B -->|sim| C[Fazer]", "  B -->|não| D[Fim]", "  C --> D"].join(
  "\n",
);

/** A ```mermaid code block, drawn: the source stays the node's text, so the page keeps it as written. */
export const Diagram = Node.create({
  name: "diagram",
  group: "block",
  content: "text*",
  marks: "",
  code: true,
  defining: true,
  parseHTML: () => [{ tag: "pre[data-diagram]", preserveWhitespace: "full" }],
  renderHTML: () => ["pre", { "data-diagram": "" }, 0],
  addCommands() {
    return {
      insertDiagram:
        () =>
        ({ commands }) =>
          commands.insertContent({ type: this.name, content: [{ type: "text", text: EXAMPLE }] }),
    };
  },
  addNodeView: () => ReactNodeViewRenderer(DiagramView),
  markdownTokenizer: {
    name: "diagram",
    level: "block",
    start: startBefore(/^```mermaid$/m),
    tokenize: (src) => {
      const match = FENCE.exec(src);
      return match ? { type: "diagram", raw: match[0], text: match[1] ?? "" } : undefined;
    },
  },
  parseMarkdown: (token, h) => h.createNode("diagram", undefined, token.text ? [h.createTextNode(token.text)] : []),
  renderMarkdown: (node) => markdownOf((node.content ?? []).map((kid) => kid.text ?? "").join("")),
});

/** For the "/" menu: `insertDiagram()` puts a small flowchart to start from. */
export const diagramKinds: BlockKind[] = [{ id: "diagram", group: "blocks" }];
