import { markdown } from "@codemirror/lang-markdown";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { tags } from "@lezer/highlight";
import { EditorView, minimalSetup } from "codemirror";
import { useEffect, useRef } from "react";

const theme = EditorView.theme({
  "&": { backgroundColor: "transparent", color: "var(--text-2)", fontSize: "12px" },
  "&.cm-focused": { outline: "none" },
  ".cm-scroller": { fontFamily: "var(--font-mono)", lineHeight: "22px" },
  ".cm-content": { padding: "0", caretColor: "var(--text)" },
  ".cm-line": { padding: "0" },
  ".cm-cursor": { borderLeftColor: "var(--text)" },
  "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection": {
    backgroundColor: "var(--accent-soft)",
  },
});

// Only tokens, so both themes read; replaces CodeMirror's default palette.
const highlight = HighlightStyle.define([
  { tag: tags.heading, color: "var(--text)", fontWeight: "500" },
  { tag: [tags.processingInstruction, tags.comment, tags.meta, tags.url], color: "var(--text-3)" },
  { tag: tags.link, color: "var(--text)" },
  { tag: tags.strong, fontWeight: "500" },
  { tag: tags.emphasis, fontStyle: "italic" },
]);

/** The Markdown source. Uncontrolled: `value` is only the text it opens with. */
export function SourceEditor({ value, label, onChange }: { value: string; label: string; onChange: (text: string) => void }) {
  const parent = useRef<HTMLDivElement>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    const view = new EditorView({
      doc: value,
      parent: parent.current!,
      extensions: [
        minimalSetup,
        markdown(),
        syntaxHighlighting(highlight),
        theme,
        EditorView.lineWrapping,
        EditorView.contentAttributes.of({ "aria-label": label }),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) onChangeRef.current(update.state.doc.toString());
        }),
      ],
    });
    return () => view.destroy();
    // The editor owns its text once open; a new `value` comes in by remounting it with a new key.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <div ref={parent} />;
}
