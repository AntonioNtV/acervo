import { Node, type Editor } from "@tiptap/core";
import type { Transaction } from "@tiptap/pm/state";
import { NodeViewWrapper, ReactNodeViewRenderer, type ReactNodeViewProps } from "@tiptap/react";
import { useContext, useRef, useState } from "react";
import { useAttachmentLink } from "../../data/attachments";
import { ApiError } from "../../data/request";
import { useI18n } from "../../i18n";
import { MediaToolbar, type MediaTool } from "../../ui/MediaToolbar";
import { UploadArea } from "../../ui/UploadArea";
import type { BlockKind } from "../blocks";
import { startBefore } from "../tokenize";
import { attachmentName, uploadInto } from "./attachment";
import { PageContext } from "./generated";
import "./image.css";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    attachmentImage: { insertImage: () => ReturnType };
  }
}

// A line holding only `![caption](arquivos/name)`; any other image stays raw text.
const LINE = /^!\[([^\]\n]*)\]\((arquivos\/[^/?#)\s]+)\)[ \t]*(?:\n|$)/;

const markdownOf = (attrs: Record<string, unknown> | undefined) =>
  attrs?.src ? `![${attrs.caption ?? ""}](${attrs.src})` : "";

/** Uploads `files` into the page at the selection: images as image blocks, anything else as file blocks. */
export function insertAttachment(editor: Editor, files: File[], pageId: string) {
  for (const file of files) {
    const type = editor.schema.nodes[file.type.startsWith("image/") ? "attachmentImage" : "attachmentFile"]!;
    const node = type.create({ progress: 0 });
    editor.view.dispatch(editor.state.tr.replaceSelectionWith(node));
    let pos: number | undefined;
    editor.state.doc.descendants((child, at) => {
      if (child === node) pos = at;
      return pos === undefined;
    });
    // Mapped to the left, a block whose attrs changed keeps its position; one deleted no longer has a block there
    // still uploading (shortcut: another upload landing on that same spot would take its place; rare enough).
    const follow = ({ transaction }: { transaction: Transaction }) => {
      if (pos !== undefined) pos = transaction.mapping.map(pos, -1);
    };
    const getPos = () => {
      const found = pos === undefined ? null : editor.state.doc.nodeAt(pos);
      return found?.type === type && found.attrs.progress !== null ? pos : undefined;
    };
    editor.on("transaction", follow);
    void uploadInto(editor, getPos, file, pageId).finally(() => editor.off("transaction", follow));
  }
}

export function ImageView({ editor, node, getPos, updateAttributes }: ReactNodeViewProps) {
  const { t } = useI18n();
  const pageId = useContext(PageContext)?.nodeId ?? "";
  const src = String(node.attrs.src ?? "");
  const caption = String(node.attrs.caption ?? "");
  const progress = node.attrs.progress as number | null;
  const error = node.attrs.error as string | null;
  const name = src ? attachmentName(src) : null;
  const link = useAttachmentLink(pageId, name);
  const [captioning, setCaptioning] = useState(false);
  const chooser = useRef<HTMLInputElement>(null);
  // The last file chosen here, sent again by Tentar de novo; one pasted into the page is chosen again instead.
  const lastFile = useRef<File | null>(null);

  const upload = (file: File | undefined) => {
    if (!file) return;
    lastFile.current = file;
    void uploadInto(editor, getPos, file, pageId);
  };
  const retry = () => (lastFile.current ? upload(lastFile.current) : updateAttributes({ error: null }));
  const act = (tool: MediaTool) => {
    if (tool === "caption") setCaptioning(true);
    if (tool === "replace") chooser.current?.click();
    if (tool === "download" && link.data && name)
      Object.assign(document.createElement("a"), { href: link.data.src, download: name }).click();
  };

  const message =
    error === "attachment_too_large" ? t("editor.media.tooLarge") : error === "network" ? t("errors.network") : t("errors.other");
  const missing = link.isError && link.error instanceof ApiError && link.error.status === 404;

  let media;
  if (progress !== null) media = <UploadArea kind="image" progress={progress * 100} onFiles={() => {}} onRetry={() => {}} />;
  else if (!src || error)
    media = <UploadArea kind="image" error={error ? message : undefined} onFiles={(files) => upload(files[0])} onRetry={retry} />;
  else if (link.isError)
    media = (
      <div className="attachment-image-missing" role="alert">
        {missing ? t("editor.media.missing") : t("errors.other")}
      </div>
    );
  else
    media = (
      <div className="group relative">
        {link.data && <img className="attachment-image-img" src={link.data.src} alt={caption} loading="lazy" />}
        <MediaToolbar floating tools={["caption", "replace", "download"]} onAction={act} />
      </div>
    );

  return (
    <NodeViewWrapper as="figure" className="attachment-image" contentEditable={false}>
      {media}
      <input
        ref={chooser}
        type="file"
        hidden
        accept="image/*"
        aria-label={t("editor.media.replace")}
        onChange={(event) => {
          upload(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
      {src && (captioning || caption) && (
        <input
          className="attachment-image-caption"
          aria-label={t("editor.media.caption")}
          placeholder={t("editor.media.caption")}
          value={caption}
          autoFocus={captioning}
          // A `]` or a line break would end the Markdown image early.
          onChange={(event) => updateAttributes({ caption: event.target.value.replace(/[\]\n]/g, "") })}
          onBlur={() => setCaptioning(false)}
        />
      )}
    </NodeViewWrapper>
  );
}

/** `![Fachada](arquivos/fachada.jpg)` alone on its line: an image of the page's attachments, with its caption. */
export const AttachmentImage = Node.create({
  name: "attachmentImage",
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,
  addAttributes: () => ({
    src: { default: null },
    caption: { default: "" },
    progress: { default: null, rendered: false },
    error: { default: null, rendered: false },
  }),
  parseHTML: () => [
    {
      tag: "figure[data-attachment-image]",
      getAttrs: (el) => ({
        src: (el as HTMLElement).dataset.attachmentImage || null,
        caption: (el as HTMLElement).dataset.caption ?? "",
      }),
    },
  ],
  renderHTML: ({ node }) => [
    "figure",
    { "data-attachment-image": node.attrs.src ?? "", "data-caption": node.attrs.caption },
    markdownOf(node.attrs),
  ],
  renderText: ({ node }) => markdownOf(node.attrs),
  addCommands() {
    return {
      insertImage:
        () =>
        ({ commands }) =>
          commands.insertContent({ type: this.name }),
    };
  },
  addNodeView: () =>
    ReactNodeViewRenderer(ImageView, {
      // The editor would take the clicks and keys of the toolbar, the upload area and the caption.
      stopEvent: ({ event }) => event.target instanceof Element && event.target.closest("button, input") !== null,
    }),
  markdownTokenizer: {
    name: "attachmentImage",
    level: "block",
    start: startBefore(/^!\[[^\]\n]*\]\(arquivos\//m),
    tokenize: (src) => {
      const match = LINE.exec(src);
      return match ? { type: "attachmentImage", raw: match[0], caption: match[1], src: match[2] } : undefined;
    },
  },
  parseMarkdown: (token, h) => h.createNode("attachmentImage", { src: token.src, caption: token.caption }),
  renderMarkdown: (node) => markdownOf(node.attrs),
});

/** Inserted with `insertImage()`: the empty block, which asks for the image. */
export const imageKinds: BlockKind[] = [{ id: "image", group: "blocks" }];
