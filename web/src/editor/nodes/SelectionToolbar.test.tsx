import "@testing-library/jest-dom/vitest";
import { Editor } from "@tiptap/core";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { I18nProvider } from "../../i18n";
import { blockExtensions } from "../extensions";
import { markExtensions } from "./marks";
import { SelectionToolbar } from "./SelectionToolbar";

// jsdom has no layout, and ProseMirror measures text ranges to place things.
Range.prototype.getClientRects ??= () => [] as unknown as DOMRectList;
Range.prototype.getBoundingClientRect ??= () => new DOMRect();

function renderToolbar() {
  const editor = new Editor({
    extensions: [...blockExtensions, ...markExtensions],
    content: { type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text: "Prazo de 3 dias" }] }] },
  });
  render(
    <I18nProvider>
      <SelectionToolbar editor={editor} />
    </I18nProvider>,
  );
  return editor;
}

describe("SelectionToolbar", () => {
  it("shows over a text selection", () => {
    const editor = renderToolbar();
    expect(screen.queryByRole("toolbar")).not.toBeInTheDocument();

    act(() => void editor.commands.setTextSelection({ from: 1, to: 6 }));

    expect(screen.getByRole("toolbar")).toBeInTheDocument();
  });

  it("picking a color applies the text color mark", () => {
    const editor = renderToolbar();
    act(() => void editor.commands.setTextSelection({ from: 1, to: 6 }));

    const buttons = within(screen.getByRole("toolbar")).getAllByRole("button");
    fireEvent.click(buttons.at(-1)!);
    fireEvent.click(screen.getByRole("menuitemradio", { name: /Azul/ }));

    expect(editor.getJSON().content?.[0]?.content?.[0]).toEqual({
      type: "text",
      text: "Prazo",
      marks: [{ type: "textColor", attrs: { color: "blue" } }],
    });
  });
});
