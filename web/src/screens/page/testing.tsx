import type { Editor } from "@tiptap/core";
import { act, screen } from "@testing-library/react";
import type { NodeDetail, PageVersion } from "../../api/client";
import { nodeFields, renderInBase } from "../../api/testing";
import { NodeView } from "../../app/NodeView";

// jsdom has no layout, and ProseMirror measures text ranges.
Range.prototype.getClientRects ??= () => [] as unknown as DOMRectList;
Range.prototype.getBoundingClientRect ??= () => new DOMRect();
document.elementFromPoint ??= () => null;

export function pageNode(page: Partial<NonNullable<NodeDetail["page"]>> = {}): NodeDetail {
  return {
    ...nodeFields,
    id: "page-1",
    kb_id: "kb-1",
    parent_id: "folder-1",
    kind: "page",
    title: "Emissão de apólice",
    deleted_at: null,
    path: "Bradesco/Residencial/Emissão de apólice",
    page: {
      version_id: "v2",
      markdown: "## Documentos\n",
      revision: 4,
      saved_at: "2026-10-14T16:10:00Z",
      links: {},
      sections: [],
      ...page,
    },
    file: null,
    versions: 2,
  };
}

export const versions: PageVersion[] = [
  {
    id: "v2",
    created_at: "2026-10-14T16:10:00Z",
    edit_started_at: "2026-10-14T15:58:00Z",
    edit_ended_at: "2026-10-14T16:10:00Z",
  },
  { id: "v1", created_at: "2026-10-14T11:03:00Z", edit_started_at: null, edit_ended_at: null },
];

export function renderPage() {
  return renderInBase(<NodeView />, "/kbs/kb-1/n/page-1");
}

/** Appends a paragraph to the page, as typing does; jsdom cannot drive ProseMirror's input itself. */
export function typeInPage(text: string) {
  const { editor } = screen.getByRole("textbox", { name: "Texto da página" }) as HTMLElement & { editor: Editor };
  act(() => {
    editor.commands.insertContentAt(editor.state.doc.content.size, { type: "paragraph", content: [{ type: "text", text }] });
  });
}
