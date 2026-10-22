import { screen } from "@testing-library/react";
import { EditorView } from "codemirror";
import type { NodeDetail, Version } from "../../api/queries";
import { NodeView } from "../../app/NodeView";
import { renderInBase } from "../../testing";

// jsdom has no layout, and CodeMirror measures text ranges.
Range.prototype.getClientRects ??= () => [] as unknown as DOMRectList;
Range.prototype.getBoundingClientRect ??= () => new DOMRect();

export function pageNode(page: Partial<NonNullable<NodeDetail["page"]>> = {}): NodeDetail {
  return {
    id: "page-1",
    kb_id: "kb-1",
    parent_id: "folder-1",
    kind: "page",
    title: "Emissão de apólice",
    deleted_at: null,
    path: "Bradesco/Residencial/Emissão de apólice",
    page: { version_id: "v2", markdown: "## Documentos\n", draft: null, links: {}, sections: [], ...page },
    file: null,
    versions: 2,
  };
}

export const versions: Version[] = [
  { id: "v2", created_at: "2026-10-14T16:10:00Z", author: "user", size: null },
  { id: "v1", created_at: "2026-10-14T11:03:00Z", author: "user", size: null },
];

export function renderPage() {
  return renderInBase(<NodeView />, "/kbs/kb-1/n/page-1");
}

/** Appends `text` to the Markdown source, as typing does; jsdom cannot drive CodeMirror's input itself. */
export function typeInSource(text: string) {
  const view = EditorView.findFromDOM(screen.getByRole("textbox", { name: "Fonte em Markdown" }))!;
  view.dispatch({ changes: { from: view.state.doc.length, insert: text } });
}
