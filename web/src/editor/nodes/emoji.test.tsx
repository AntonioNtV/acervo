import "@testing-library/jest-dom/vitest";
import { act, render, screen } from "@testing-library/react";
import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import { I18nProvider } from "../../i18n";
import { blockExtensions } from "../extensions";
import { parseMarkdown, serializeMarkdown } from "../markdown";
import { Emoji } from "./emoji";

// jsdom has no layout, and ProseMirror measures text ranges to scroll the selection into view.
Range.prototype.getClientRects ??= () => [] as unknown as DOMRectList;
Range.prototype.getBoundingClientRect ??= () => new DOMRect();

function renderEditor(markdown: string) {
  let editor: Editor | null = null;
  function Harness() {
    editor = useEditor({ extensions: [Emoji, ...blockExtensions], content: parseMarkdown(markdown).doc });
    return <EditorContent editor={editor} />;
  }
  render(
    <I18nProvider>
      <Harness />
    </I18nProvider>,
  );
  return editor!;
}

/** Types as the keyboard does, through the triggers; the same helper as BlockEditor's tests. */
function type(editor: Editor, text: string) {
  act(() => {
    for (const char of text) {
      const { view } = editor;
      const { from, to } = view.state.selection;
      const handled = view.someProp("handleTextInput", (f) => f(view, from, to, char, () => view.state.tr));
      if (!handled) view.dispatch(view.state.tr.insertText(char, from, to));
    }
  });
}

function press(editor: Editor, key: string) {
  let handled = false;
  act(() => {
    handled = !!editor.view.someProp("handleKeyDown", (f) => f(editor.view, new KeyboardEvent("keydown", { key })));
  });
  return handled;
}

const markdownOf = (editor: Editor) => serializeMarkdown(editor.state.doc, { lead: "", chunks: [], nodes: [] });

describe("Emoji", () => {
  it(":cas then Enter leaves 🏠 in the text and in the Markdown", async () => {
    const editor = renderEditor("");

    type(editor, "Casa :cas");
    await screen.findByRole("button", { name: "casa" });
    expect(press(editor, "Enter")).toBe(true);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(markdownOf(editor)).toBe("Casa 🏠\n");
  });

  it("12:30 and : inside code open nothing", async () => {
    const editor = renderEditor("```\nx\n```\n\n`ab`\n\nÀs\n");
    const typeAt = async (pos: number, text: string) => {
      act(() => {
        editor.commands.setTextSelection(pos);
      });
      type(editor, text);
      await act(async () => {});
      return screen.queryByRole("dialog");
    };

    expect(await typeAt(2, " :cas")).not.toBeInTheDocument();
    expect(await typeAt(10, " :cas")).not.toBeInTheDocument();
    expect(await typeAt(editor.state.doc.content.size - 1, " 12:30")).not.toBeInTheDocument();
    expect(markdownOf(editor)).toBe("```\nx :cas\n```\n\n`a :casb`\n\nÀs 12:30\n");
  });
});
