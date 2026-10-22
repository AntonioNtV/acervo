import { rawFileUrl, type NodeDetail } from "../../api/queries";
import { useI18n } from "../../i18n";
import { FileHeader } from "./FileHeader";
import { formatSize } from "./format";
import { PdfViewer } from "../../viewer/PdfViewer";

type Viewer = "pdf" | "image" | "other";

function viewerFor(mime: string): Viewer {
  if (mime === "application/pdf") return "pdf";
  return mime.startsWith("image/") ? "image" : "other";
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
      ) : (
        <OtherFile node={node} />
      )}
    </div>
  );
}

function ImageView({ node }: { node: NodeDetail }) {
  return (
    <>
      <FileHeader node={node} />
      <div className="flex min-h-0 flex-1 items-center justify-center p-6">
        <img
          src={`${rawFileUrl(node.id)}?v=${node.file?.sha256 ?? ""}`}
          alt={node.title}
          className="block max-h-full max-w-full object-contain"
        />
      </div>
    </>
  );
}

function OtherFile({ node }: { node: NodeDetail }) {
  const { t, lang } = useI18n();
  const file = node.file;
  if (!file) return null;
  const rows: Array<[string, string]> = [
    [t("pdf.type"), file.mime],
    [t("pdf.size"), formatSize(file.size, lang)],
    [t("pdf.versions"), t(node.versions === 1 ? "pdf.versions.one" : "pdf.versions.other", { n: node.versions })],
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
