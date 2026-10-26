import { Extension, type Editor } from "@tiptap/core";
import { PluginKey } from "@tiptap/pm/state";
import { ReactRenderer } from "@tiptap/react";
import { exitSuggestion, Suggestion } from "@tiptap/suggestion";
import { EmojiPicker, findEmojis } from "../../ui/EmojiPicker";

const key = new PluginKey("emoji");

type Props = { editor: Editor; query: string; rect: DOMRect | null; onPick: (emoji: string) => void };

/** The picker pinned under the caret; the editor keeps the focus and the typing. */
function CaretPicker({ editor, query, rect, onPick }: Props) {
  return (
    <div
      style={{ position: "fixed", left: rect?.left ?? 0, top: rect?.top ?? 0, height: rect?.height ?? 0 }}
      // Keeps the editor's selection, so a click replaces the ":name" that was typed.
      onMouseDown={(event) => event.preventDefault()}
    >
      <EmojiPicker query={query} onPick={onPick} onClose={() => exitSuggestion(editor.view, key)} />
    </div>
  );
}

/** ":" and a name, after a space or at line start, opens the emoji picker; the chosen emoji goes in as text. */
export const Emoji = Extension.create({
  name: "emoji",
  addProseMirrorPlugins() {
    const editor = this.editor;
    const pick = (emoji: string) => {
      const { range } = key.getState(editor.state);
      editor.chain().focus().insertContentAt(range, emoji).run();
    };
    return [
      Suggestion({
        editor,
        char: ":",
        pluginKey: key,
        allow: ({ state, range }) =>
          !state.doc.resolve(range.from).parent.type.spec.code &&
          !state.doc.rangeHasMark(range.from, range.to, state.schema.marks.code!),
        shouldShow: ({ query }) => /^\p{L}/u.test(query),
        render: () => {
          let picker: ReactRenderer | null = null;
          const show = ({ query, clientRect }: { query: string; clientRect?: (() => DOMRect | null) | null }) => {
            const props = { editor, query, rect: clientRect?.() ?? null, onPick: pick };
            if (picker) return picker.updateProps(props);
            picker = new ReactRenderer(CaretPicker, { editor, props });
            document.body.append(picker.element);
          };
          return {
            onStart: show,
            onUpdate: show,
            onExit: () => {
              picker?.element.remove();
              picker?.destroy();
              picker = null;
            },
            onKeyDown: ({ event }) => {
              const first = findEmojis(key.getState(editor.state).query)[0];
              if (event.key !== "Enter" || !first) return false;
              pick(first[0]);
              return true;
            },
          };
        },
      }),
    ];
  },
});
