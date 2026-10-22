import { useRef, useState } from "react";
import { ApiError, useRestoreVersion, useVersions, type NodeDetail } from "../../api/queries";
import { useReplaceFile } from "../../api/upload";
import { useErrorText } from "../../app/errors";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { Dialog, DialogClose } from "../../ui/Dialog";
import { DownloadLink } from "./DownloadLink";
import { formatDate, formatSize } from "./format";

/** A 409 is the file's own content, or (with its path in `detail`) another file's of the base. */
function useFileErrorText() {
  const { t } = useI18n();
  const errorText = useErrorText();
  return (error: unknown) => {
    const detail = error instanceof ApiError ? (error.body.detail as { path?: string; trashed?: boolean } | null) : null;
    const conflict = detail?.path
      ? t(detail.trashed ? "pdf.replace.duplicateTrashed" : "pdf.replace.duplicate", { path: detail.path })
      : t("pdf.replace.same");
    return errorText(error, { 409: conflict });
  };
}

/** "Substituir arquivo" and "Versões": the file's current content goes to its history, and back. */
export function FileActions({ node }: { node: NodeDetail }) {
  const { t } = useI18n();
  const input = useRef<HTMLInputElement>(null);
  const replace = useReplaceFile(node.id);
  const errorText = useFileErrorText();
  const [percent, setPercent] = useState(0);

  function pick(file: File | undefined) {
    if (!file) return;
    setPercent(0);
    replace.mutate({ file, onProgress: (loaded, total) => setPercent(total ? Math.round((loaded / total) * 100) : 0) });
  }

  return (
    <>
      {replace.isPending && (
        <span className="px-1 text-12 text-text-3 tabular-nums">{t("pdf.replace.progress", { pct: percent })}</span>
      )}
      {replace.isError && <span className="px-1 text-12 text-err">{errorText(replace.error)}</span>}
      <input
        ref={input}
        type="file"
        hidden
        aria-label={t("pdf.replace")}
        onChange={(event) => {
          pick(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
      <Button variant="quiet" size="sm" disabled={replace.isPending} onClick={() => input.current?.click()}>
        {t("pdf.replace")}
      </Button>
      <Dialog
        title={t("pdf.versions.title")}
        trigger={
          <Button variant="quiet" size="sm">
            {t("pdf.versions")}
          </Button>
        }
        footer={
          <DialogClose asChild>
            <Button>{t("pdf.versions.close")}</Button>
          </DialogClose>
        }
      >
        <VersionList nodeId={node.id} />
      </Dialog>
    </>
  );
}

function VersionList({ nodeId }: { nodeId: string }) {
  const { t, lang } = useI18n();
  const versions = useVersions(nodeId);
  const restore = useRestoreVersion(nodeId);
  const errorText = useFileErrorText();

  if (versions.isPending) return <p className="m-0 text-text-3">{t("pdf.loading")}</p>;
  if (versions.isError) return <p className="m-0 text-err">{errorText(versions.error)}</p>;
  if (versions.data.length === 0) return <p className="m-0 text-text-3">{t("pdf.versions.empty")}</p>;
  return (
    <div className="flex flex-col">
      {restore.isError && <p className="m-0 mb-2 text-12 text-err">{errorText(restore.error)}</p>}
      <ul className="m-0 flex list-none flex-col p-0">
        {versions.data.map((version) => (
          <li key={version.id} className="flex min-h-11 items-center gap-2 border-b border-line last:border-b-0">
            <span className="min-w-0 flex-1 truncate">{formatDate(version.created_at, lang)}</span>
            {version.size !== null && (
              <span className="text-12 text-text-3 tabular-nums">{formatSize(version.size, lang)}</span>
            )}
            <DownloadLink nodeId={nodeId} versionId={version.id} />
            <Button
              variant="quiet"
              size="sm"
              disabled={restore.isPending}
              onClick={() => restore.mutate(version.id)}
            >
              {t("pdf.restore")}
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
