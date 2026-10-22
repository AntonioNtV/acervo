import { Extension, type Range } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Suggestion } from "@tiptap/suggestion";
import { markdownToJSON } from "./markdown";

export type MenuState = { kind: "slash" | "page"; query: string; range: Range; rect: DOMRect | null };

/** How the plugins reach the React side, which owns the popover and its items. */
export type MenuBridge = { show: (menu: MenuState | null) => void; key: (event: KeyboardEvent) => boolean };

/** "/" opens the block menu; `[[` and `@` open the page picker. */
export function createMenus(bridge: { current: MenuBridge }) {
  return Extension.create({
    name: "blockMenus",
    addProseMirrorPlugins() {
      const menu = (kind: MenuState["kind"], char: string) =>
        Suggestion({
          editor: this.editor,
          char,
          pluginKey: new PluginKey(`menu${char}`),
          allowSpaces: kind === "page",
          allowedPrefixes: char === "[[" ? null : [" "],
          allow: ({ state, range }) => !state.doc.resolve(range.from).parent.type.spec.code,
          render: () => {
            const show = (p: { query: string; range: Range; clientRect?: (() => DOMRect | null) | null }) =>
              bridge.current.show({ kind, query: p.query, range: p.range, rect: p.clientRect?.() ?? null });
            return {
              onStart: show,
              onUpdate: show,
              onExit: () => bridge.current.show(null),
              onKeyDown: ({ event }) => bridge.current.key(event),
            };
          },
        });
      return [menu("slash", "/"), menu("page", "[["), menu("page", "@")];
    },
  });
}

/** Plain text pasted is read as Markdown, so a pasted page keeps its blocks; rich HTML goes through the schema. */
export const MarkdownPaste = Extension.create({
  name: "markdownPaste",
  addProseMirrorPlugins() {
    const editor = this.editor;
    return [
      new Plugin({
        key: new PluginKey("markdownPaste"),
        props: {
          handlePaste: (view, event) => {
            const data = event.clipboardData;
            if (!data || data.types.includes("text/html")) return false;
            const text = data.getData("text/plain");
            if (!text.trim() || view.state.selection.$from.parent.type.spec.code) return false;
            return editor.commands.insertContent(markdownToJSON(text).content ?? []);
          },
        },
      }),
    ];
  },
});
