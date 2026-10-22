import { useRef, useState } from "react";
import type { NodeDetail } from "../../api/client";
import { useFileVersions, useRestoreFileVersion } from "../../data/files";
import { ApiError } from "../../data/request";
import { useReplaceFile } from "../../data/upload";
import { useErrorText } from "../../app/errors";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { Dialog, DialogClose } from "../../ui/Dialog";
import { DownloadLink } from "./DownloadLink";
import { formatDate, formatSize } from "./format";

/** A `duplicate` names where the same content already is; `same_file` is the file's own content. */
function useFileErrorText() {
  const { t } = useI18n();
  const errorText = useErrorText();
  return (error: unknown) => {
    if (error instanceof ApiError && error.code === "duplicate") {
      const details = error.details as { path: string; trashed: boolean; history: boolean };
      const variant = details.history ? "duplicateHistory" : details.trashed ? "duplicateTrashed" : "duplicate";
      return t(`file.replace.${variant}`, { path: details.path });
    }
    return errorText(error, { same_file: t("file.replace.same") });
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
        <span className="px-1 text-12 text-text-3 tabular-nums">{t("file.replace.progress", { pct: percent })}</span>
      )}
      {replace.isError && <span className="px-1 text-12 text-err">{errorText(replace.error)}</span>}
      <input
        ref={input}
        type="file"
        hidden
        aria-label={t("file.replace")}
        onChange={(event) => {
          pick(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
      <Button variant="quiet" size="sm" disabled={replace.isPending} onClick={() => input.current?.click()}>
        {t("file.replace")}
      </Button>
      <Dialog
        title={t("file.versions.title")}
        trigger={
          <Button variant="quiet" size="sm">
            {t("file.versions")}
          </Button>
        }
        footer={
          <DialogClose asChild>
            <Button>{t("file.versions.close")}</Button>
          </DialogClose>
        }
      >
        <VersionList nodeId={node.id} title={node.title} />
      </Dialog>
    </>
  );
}

function VersionList({ nodeId, title }: { nodeId: string; title: string }) {
  const { t, lang } = useI18n();
  const versions = useFileVersions(nodeId);
  const restore = useRestoreFileVersion(nodeId);
  const errorText = useFileErrorText();

  if (versions.isPending) return <p className="m-0 text-text-3">{t("file.loading")}</p>;
  if (versions.isError) return <p className="m-0 text-err">{errorText(versions.error)}</p>;
  if (versions.data.length === 0) return <p className="m-0 text-text-3">{t("file.versions.empty")}</p>;
  return (
    <div className="flex flex-col">
      {restore.isError && <p className="m-0 mb-2 text-12 text-err">{errorText(restore.error)}</p>}
      <ul className="m-0 flex list-none flex-col p-0">
        {versions.data.map((version) => (
          <li key={version.id} className="flex min-h-11 items-center gap-2 border-b border-line last:border-b-0">
            <span className="min-w-0 flex-1 truncate">{formatDate(version.replaced_at, lang)}</span>
            <span className="text-12 text-text-3 tabular-nums">{formatSize(version.size, lang)}</span>
            <DownloadLink nodeId={nodeId} filename={title} versionId={version.id} />
            <Button
              variant="quiet"
              size="sm"
              disabled={restore.isPending}
              onClick={() => restore.mutate(version.id)}
            >
              {t("file.restore")}
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
