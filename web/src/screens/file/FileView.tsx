import { useState } from "react";
import type { NodeDetail } from "../../api/client";
import { useErrorText } from "../../app/errors";
import { useDownloadFile, useOpenFile, useRawFileUrl } from "../../data/files";
import { useI18n } from "../../i18n";
import { MediaRow } from "../../ui/MediaRow";
import { MediaToolbar } from "../../ui/MediaToolbar";
import { useReplacePicker } from "./FileActions";
import { FileHeader } from "./FileHeader";
import { formatSize } from "./format";
import { PdfViewer } from "../../viewer/PdfViewer";

type Viewer = "pdf" | "image" | "video" | "audio" | "other";

function viewerFor(mime: string): Viewer {
  if (mime === "application/pdf") return "pdf";
  const type = mime.split("/")[0];
  return type === "image" || type === "video" || type === "audio" ? type : "other";
}

/** A file node, shown as the original file; `?p=` opens a PDF at a page. */
export function FileView({ node }: { node: NodeDetail }) {
  if (!node.file) return null;
  const viewer = viewerFor(node.file.mime);
  return (
    <div className="flex h-full min-h-0 flex-col bg-desk">
      {viewer === "pdf" ? (
        <PdfViewer node={node} />
      ) : viewer === "image" ? (
        <ImageView node={node} />
      ) : viewer === "video" || viewer === "audio" ? (
        <MediaView node={node} kind={viewer} />
      ) : (
        <OtherFile node={node} />
      )}
    </div>
  );
}

function ImageView({ node }: { node: NodeDetail }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const link = useRawFileUrl(node.id, node.file?.sha256);
  const [failed, setFailed] = useState<string | null>(null);
  const replace = useReplacePicker(node.id);
  const download = useDownloadFile(node.id, node.title);
  const open = useOpenFile(node.id);
  return (
    <>
      <FileHeader node={node} />
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 p-6">
        {link.isError ? (
          <p className="m-0 text-err">{errorText(link.error)}</p>
        ) : link.data && failed === link.data ? (
          <p className="m-0 text-err">{t("file.error.image")}</p>
        ) : (
          link.data && (
            <div className="group relative flex min-h-0 max-w-full">
              <img
                src={link.data}
                alt={node.title}
                onError={() => setFailed(link.data)}
                className="block max-h-full max-w-full object-contain"
              />
              <MediaToolbar
                tools={["replace", "download", "open"]}
                floating
                onAction={(tool) => {
                  if (tool === "replace") replace.choose();
                  else if (tool === "download") download.mutate(undefined);
                  else open.mutate();
                }}
              />
            </div>
          )
        )}
        <p className="m-0 flex gap-2">
          {replace.view}
          {download.isError && <span className="px-1 text-12 text-err">{errorText(download.error)}</span>}
          {open.isError && <span className="px-1 text-12 text-err">{errorText(open.error)}</span>}
        </p>
      </div>
    </>
  );
}

function MediaView({ node, kind }: { node: NodeDetail; kind: "video" | "audio" }) {
  const errorText = useErrorText();
  const link = useRawFileUrl(node.id, node.file?.sha256);
  return (
    <>
      <FileHeader node={node} />
      <div className="flex min-h-0 flex-1 items-center justify-center overflow-auto p-6">
        {link.isError ? (
          <p className="m-0 text-err">{errorText(link.error)}</p>
        ) : (
          link.data && (
            <div className="w-full max-w-[720px]">
              <MediaRow kind={kind} name={node.title} src={link.data} onExpired={() => void link.refetch()} />
            </div>
          )
        )}
      </div>
    </>
  );
}

function OtherFile({ node }: { node: NodeDetail }) {
  const { t, lang } = useI18n();
  const file = node.file;
  if (!file) return null;
  const rows: Array<[string, string]> = [
    [t("file.type"), file.mime],
    [t("file.size"), formatSize(file.size, lang)],
    [t("file.versions"), t(node.versions === 1 ? "file.versions.one" : "file.versions.other", { n: node.versions })],
  ];
  return (
    <>
      <FileHeader node={node} />
      <div className="flex min-h-0 flex-1 justify-center overflow-auto px-6 py-8">
        <dl className="m-0 grid h-fit w-full max-w-[440px] grid-cols-[120px_minmax(0,1fr)] rounded-[10px] border border-line-2 bg-bg px-5 py-2">
          {rows.map(([label, value]) => (
            <div key={label} className="col-span-2 grid min-h-11 grid-cols-subgrid items-center border-b border-line last:border-b-0">
              <dt className="text-text-3">{label}</dt>
              <dd className="m-0 truncate">{value}</dd>
            </div>
          ))}
        </dl>
      </div>
    </>
  );
}
