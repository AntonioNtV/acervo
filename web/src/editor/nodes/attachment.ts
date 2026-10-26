import type { Editor } from "@tiptap/core";
import { uploadAttachment } from "../../data/attachments";
import { ApiError } from "../../data/request";

const HREF = /^arquivos\/([^/?#]+)$/;

/** The page attachment an `arquivos/<name>` link points at; null for any other link. */
export function attachmentName(href: string): string | null {
  return HREF.exec(href)?.[1] ?? null;
}

/**
 * Uploads `file` into the page and keeps the block at `getPos()` up to date: `progress` (0 to 1) while it goes,
 * `error` (the API's code, or "network") when it fails, and `src` (`arquivos/<name>`) once it is stored.
 * Until `src` is set the block has nothing to write to the Markdown.
 */
export async function uploadInto(editor: Editor, getPos: () => number | undefined, file: File, pageId: string) {
  const update = (attrs: Record<string, unknown>) => {
    const pos = getPos();
    const node = pos === undefined ? null : editor.state.doc.nodeAt(pos);
    if (pos === undefined || !node || editor.isDestroyed) return;
    // Progress is not an edit the person made: undo skips it.
    editor.view.dispatch(editor.state.tr.setNodeMarkup(pos, undefined, { ...node.attrs, ...attrs }).setMeta("addToHistory", false));
  };
  update({ progress: 0, error: null });
  try {
    const attachment = await uploadAttachment(pageId, file, (loaded, total) => update({ progress: total ? loaded / total : 0 }));
    update({ src: `arquivos/${attachment.name}`, progress: null });
  } catch (error) {
    update({ progress: null, error: error instanceof ApiError && error.code ? error.code : "network" });
  }
}
