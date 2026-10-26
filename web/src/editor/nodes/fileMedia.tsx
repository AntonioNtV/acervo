import { Node } from "@tiptap/core";
import { NodeViewWrapper, ReactNodeViewRenderer, type ReactNodeViewProps } from "@tiptap/react";
import { useQuery } from "@tanstack/react-query";
import { useContext, useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import { useErrorText } from "../../app/errors";
import { useAttachmentLink } from "../../data/attachments";
import { ApiError } from "../../data/request";
import { useI18n } from "../../i18n";
import { formatSize } from "../../screens/file/format";
import { FileName } from "../../ui/FileName";
import { Icon } from "../../ui/Icon";
import { MediaRow } from "../../ui/MediaRow";
import { UploadArea } from "../../ui/UploadArea";
import { AttachmentPdfDialog } from "../../viewer/AttachmentPdfDialog";
import type { BlockKind } from "../blocks";
import { startBefore } from "../tokenize";
import { attachmentName, uploadInto } from "./attachment";
import { PageContext } from "./generated";
import "./fileMedia.css";

export type MediaKind = "file" | "video" | "audio";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    attachmentFile: { insertAttachmentFile: (kind: MediaKind) => ReturnType };
  }
}

const EXTENSIONS: Record<Exclude<MediaKind, "file">, string[]> = {
  video: ["mp4", "webm", "mov"],
  audio: ["mp3", "m4a", "wav", "ogg"],
};

const extOf = (name: string) => /\.([^.]+)$/.exec(name)?.[1]?.toLowerCase() ?? "";

/** Played in the page or offered for download, by the attachment's extension. */
export function mediaKind(name: string): MediaKind {
  const ext = extOf(name);
  return EXTENSIONS.video.includes(ext) ? "video" : EXTENSIONS.audio.includes(ext) ? "audio" : "file";
}

const ACCEPT: Record<MediaKind, string> = {
  file: "",
  video: EXTENSIONS.video.map((ext) => `.${ext}`).join(","),
  audio: EXTENSIONS.audio.map((ext) => `.${ext}`).join(","),
};

// A paragraph holding only the link: a link with text around it, or a line after it, stays a link.
const LINE = /^\[([^[\]\n]+)\]\((arquivos\/[^\s()]+)\)[ \t]*(?:\n(?=[ \t]*(?:\n|$))|\n?$)/;

const markdownOf = (attrs: Record<string, unknown> | undefined) => {
  const src = attrs?.src as string | null | undefined;
  // Nothing is written until the upload ends.
  return src ? `[${attrs?.label || attachmentName(src)}](${src})` : "";
};

/** The attachment's size from a one-byte range, which the API answers with the whole length. */
function useAttachmentSize(pageId: string, name: string | null) {
  return useQuery({
    queryKey: ["attachment-size", pageId, name],
    enabled: name !== null,
    staleTime: Infinity,
    queryFn: async () => {
      const { data, response } = await api.GET("/v1/pages/{node_id}/attachments/{name}/raw", {
        params: { path: { node_id: pageId, name: name! }, header: { range: "bytes=0-0" } },
        parseAs: "stream",
      });
      void data?.cancel();
      return Number(response.headers.get("Content-Range")?.split("/")[1]) || null;
    },
  });
}

function pickFile(accept: string, onFile: (file: File) => void) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = accept;
  input.onchange = () => input.files?.[0] && onFile(input.files[0]);
  input.click();
}

export function AttachmentFileView({ editor, node, getPos }: ReactNodeViewProps) {
  const { t, lang } = useI18n();
  const errorText = useErrorText();
  const pageId = useContext(PageContext)?.nodeId ?? null;
  const src = node.attrs.src as string | null;
  const name = src ? attachmentName(src) : null;
  const kind: MediaKind = name ? mediaKind(name) : node.attrs.kind;
  const progress = node.attrs.progress as number | null;
  const error = node.attrs.error as string | null;
  const choosing = Boolean(node.attrs.choosing);
  const sent = useRef<File | null>(null);
  const [reading, setReading] = useState(false);
  const link = useAttachmentLink(pageId ?? "", pageId ? name : null);
  const size = useAttachmentSize(pageId ?? "", pageId && kind === "file" ? name : null);

  // Just inserted from the "/" menu: the file chooser opens at once, for that kind of file.
  useEffect(() => {
    if (!choosing) return;
    const pos = getPos();
    if (pos !== undefined)
      editor.view.dispatch(editor.state.tr.setNodeAttribute(pos, "choosing", false).setMeta("addToHistory", false));
    pickFile(ACCEPT[kind], (file) => {
      sent.current = file;
      if (pageId) void uploadInto(editor, getPos, file, pageId);
    });
  }, [choosing, editor, getPos, kind, pageId]);

  // shortcut: only the first of several dropped or chosen files is sent, until card 03's insertAttachment is wired.
  const upload = (files: File[]) => {
    const [file] = files;
    sent.current = file ?? null;
    if (file && pageId) void uploadInto(editor, getPos, file, pageId);
  };

  const download = async () => {
    const { data } = await link.refetch();
    if (!data) return;
    const anchor = document.createElement("a");
    anchor.href = data.src;
    anchor.download = name ?? "";
    anchor.click();
  };

  if (!name)
    return (
      <NodeViewWrapper contentEditable={false} className="attachment-file">
        <UploadArea
          kind="file"
          progress={progress === null ? undefined : progress * 100}
          name={sent.current?.name}
          error={error ? t(error === "attachment_too_large" ? "editor.media.tooLarge" : "media.failed") : undefined}
          onFiles={upload}
          onRetry={() => upload(sent.current ? [sent.current] : [])}
        />
      </NodeViewWrapper>
    );

  const ext = extOf(name);
  const label = String(node.attrs.label || name);
  const title = label.toLowerCase().endsWith(`.${ext}`) ? label.slice(0, -ext.length - 1) : label;
  const missing = link.error instanceof ApiError && link.error.status === 404;

  return (
    <NodeViewWrapper contentEditable={false} className="attachment-file">
      {link.isError ? (
        <div role="alert" className="attachment-file-missing">
          <Icon name="file" className="text-text-3" />
          <FileName title={title} ext={ext} className="min-w-0 flex-1 truncate" />
          <span className="text-12 text-err">{missing ? t("editor.media.missing") : errorText(link.error)}</span>
        </div>
      ) : kind === "file" ? (
        <MediaRow
          kind="file"
          name={title}
          ext={ext}
          size={size.data ? formatSize(size.data, lang) : undefined}
          onDownload={() => void download()}
          onOpen={ext === "pdf" && pageId ? () => setReading(true) : undefined}
          onRetry={() => void link.refetch()}
        />
      ) : (
        link.data && (
          <MediaRow
            kind={kind}
            name={title}
            ext={ext}
            src={link.data.src}
            onExpired={() => void link.refetch()}
            onDownload={() => void download()}
          />
        )
      )}
      {reading && pageId && <AttachmentPdfDialog pageId={pageId} name={name} onClose={() => setReading(false)} />}
    </NodeViewWrapper>
  );
}

/** `[contrato.pdf](arquivos/contrato.pdf)` alone in a paragraph: a file of the page, a video or an audio. */
export const AttachmentFile = Node.create({
  name: "attachmentFile",
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,
  addAttributes: () => ({
    src: { default: null },
    label: { default: "" },
    // Which file the empty block asks for; once sent, the extension says.
    kind: { default: "file", rendered: false },
    choosing: { default: false, rendered: false },
    progress: { default: null, rendered: false },
    error: { default: null, rendered: false },
  }),
  parseHTML: () => [
    {
      tag: "div[data-attachment-file]",
      getAttrs: (el) => ({
        src: (el as HTMLElement).dataset.attachmentFile || null,
        label: (el as HTMLElement).dataset.label ?? "",
      }),
    },
  ],
  renderHTML: ({ node }) => [
    "div",
    { "data-attachment-file": node.attrs.src ?? "", "data-label": node.attrs.label },
    markdownOf(node.attrs),
  ],
  renderText: ({ node }) => markdownOf(node.attrs),
  addCommands() {
    return {
      insertAttachmentFile:
        (kind) =>
        ({ commands }) =>
          commands.insertContent({ type: this.name, attrs: { kind, choosing: true } }),
    };
  },
  addNodeView: () =>
    ReactNodeViewRenderer(AttachmentFileView, {
      // The editor would select the block on mousedown and swallow the click of Enviar, Abrir, Baixar and Tocar.
      stopEvent: ({ event }) => event.target instanceof Element && event.target.closest("button, [role=button]") !== null,
    }),
  markdownTokenizer: {
    name: "attachmentFile",
    level: "block",
    // Never cuts a paragraph: a link on a line of a longer paragraph stays in it.
    start: startBefore(/(?!)/),
    tokenize: (src) => {
      const match = LINE.exec(src);
      return match && attachmentName(match[2]!)
        ? { type: "attachmentFile", raw: match[0], label: match[1], src: match[2] }
        : undefined;
    },
  },
  parseMarkdown: (token, h) => h.createNode("attachmentFile", { src: token.src, label: token.label }),
  renderMarkdown: (node) => markdownOf(node.attrs),
});

/** For the "/" menu: each runs `insertAttachmentFile(id)`, which opens the file chooser for that kind. */
export const fileMediaKinds = [
  { id: "file", group: "blocks" },
  { id: "video", group: "blocks" },
  { id: "audio", group: "blocks" },
] satisfies BlockKind[];
