import { TextSelection } from "@tiptap/pm/state";
import { useEditorState, type Editor } from "@tiptap/react";
import { useState } from "react";
import { useI18n } from "../../i18n";
import { ColorMenu, type TextColor } from "../../ui/ColorMenu";
import { IconButton } from "../../ui/IconButton";

// A letter for each mark, drawn as the mark it applies.
const MARKS: Array<[mark: string, glyph: string, look: string]> = [
  ["bold", "B", "font-bold"],
  ["italic", "I", "italic font-serif"],
  ["strike", "S", "line-through"],
  ["code", "</>", "font-mono text-12"],
  ["underline", "U", "underline"],
];

/** The marks of a text selection, floating over it while it is not empty and not in code. */
export function SelectionToolbar({ editor }: { editor: Editor }) {
  const { t } = useI18n();
  const [colorOpen, setColorOpen] = useState(false);
  const state = useEditorState({
    editor,
    selector: ({ editor: e }) => {
      const { selection } = e.state;
      if (!(selection instanceof TextSelection) || selection.empty || selection.$from.parent.type.spec.code) return null;
      const start = e.view.coordsAtPos(selection.from);
      return {
        left: start.left,
        top: start.top,
        active: MARKS.map(([mark]) => e.isActive(mark)),
        color: (e.getAttributes("textColor").color as TextColor | undefined) ?? null,
        highlight: e.isActive("highlight"),
      };
    },
  });
  if (!state) return null;

  return (
    <div
      role="toolbar"
      aria-label={t("editor.format.label")}
      style={{ left: state.left, top: state.top - 6 }}
      className="fixed z-30 inline-flex -translate-y-full gap-0.5 rounded-[8px] border border-line-2 bg-bg p-0.5"
      // Keeps the editor's selection, so a mark applies to what is selected.
      onMouseDown={(event) => event.preventDefault()}
    >
      {MARKS.map(([mark, glyph, look], i) => (
        <IconButton
          key={mark}
          aria-label={t(`editor.format.${mark}`)}
          aria-pressed={state.active[i]}
          onClick={() => editor.chain().toggleMark(mark).run()}
        >
          <span aria-hidden className={`text-13 ${look}`}>{glyph}</span>
        </IconButton>
      ))}
      <IconButton
        aria-label={t("editor.format.color")}
        aria-expanded={colorOpen}
        aria-haspopup="menu"
        onClick={() => setColorOpen((open) => !open)}
      >
        <span aria-hidden className="text-13 font-medium underline decoration-2" style={state.color ? { color: `var(--tc-${state.color})` } : undefined}>
          A
        </span>
      </IconButton>
      {colorOpen && (
        <div className="absolute top-full left-0 mt-1.5">
          <ColorMenu
            color={state.color}
            highlight={state.highlight}
            onColor={(color) => {
              if (color) editor.chain().setMark("textColor", { color }).run();
              else editor.chain().unsetMark("textColor").run();
              setColorOpen(false);
            }}
            onHighlight={() => editor.chain().toggleMark("highlight").run()}
            onClose={() => setColorOpen(false)}
          />
        </div>
      )}
    </div>
  );
}
