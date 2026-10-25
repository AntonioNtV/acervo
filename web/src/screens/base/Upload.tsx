import { useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../../data/request";
import { useDownloadFile } from "../../data/files";
import { useUploadFile } from "../../data/upload";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { cx } from "../../ui/cx";
import { MediaRow } from "../../ui/MediaRow";
import { splitExt } from "../../ui/names";
import { useTreeErrorText } from "./names";

export type UploadRow = {
  id: number;
  kbId: string;
  parentId: string | null;
  file: File;
  name: string;
  /** The node it became, once done. */
  nodeId?: string;
  percent: number;
  state: "sending" | "done" | "duplicate" | "error";
  message?: string;
  duplicate?: { node_id: string; path: string; trashed: boolean; history?: boolean };
};

// Module state, so a drop on the tree and the folder view's button feed the same list in the tree column.
let rows: UploadRow[] = [];
let nextId = 0;
const listeners = new Set<() => void>();

function update(next: UploadRow[]) {
  rows = next;
  for (const listener of listeners) listener();
}

function patch(id: number, change: Partial<UploadRow>) {
  update(rows.map((row) => (row.id === id ? { ...row, ...change } : row)));
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function clearUploads(kbId: string) {
  update(rows.filter((row) => row.kbId !== kbId || row.state === "sending"));
}

export function useUploads() {
  return useSyncExternalStore(subscribe, () => rows);
}

/** Sends a row's file again to the same folder, in the same row. */
export function useRetryUpload(kbId: string) {
  const upload = useUploadFile(kbId);
  const errorText = useTreeErrorText();
  return ({ id, file, parentId }: UploadRow) => {
    patch(id, { state: "sending", percent: 0, message: undefined });
    upload
      .mutateAsync({
        parentId,
        file,
        onProgress: (loaded, total) => patch(id, { percent: total ? Math.round((loaded / total) * 100) : 0 }),
      })
      .then(
        (node) => patch(id, { state: "done", percent: 100, nodeId: node.id }),
        (error: unknown) => {
          if (error instanceof ApiError && error.code === "duplicate") {
            patch(id, { state: "duplicate", duplicate: error.details as UploadRow["duplicate"] });
          } else {
            patch(id, { state: "error", message: errorText(error) });
          }
        },
      );
  };
}

/** Sends each file into `parentId` (null for the root), one row of progress per file. */
export function useStartUpload(kbId: string) {
  const send = useRetryUpload(kbId);
  return (files: Iterable<File>, parentId: string | null) => {
    for (const file of files) {
      const row: UploadRow = { id: nextId++, kbId, parentId, file, name: file.name, percent: 0, state: "sending" };
      update([...rows, row]);
      send(row);
    }
  };
}

export function UploadButton({ kbId, parentId }: { kbId: string; parentId: string | null }) {
  const { t } = useI18n();
  const start = useStartUpload(kbId);
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <Button onClick={() => input.current?.click()}>{t("base.upload")}</Button>
      <input
        ref={input}
        type="file"
        multiple
        hidden
        aria-label={t("base.upload")}
        onChange={(event) => {
          start(Array.from(event.target.files ?? []), parentId);
          event.target.value = "";
        }}
      />
    </>
  );
}

export function UploadGlyph() {
  return (
    <svg
      viewBox="0 0 24 24"
      width={14}
      height={14}
      aria-hidden="true"
      className="shrink-0 fill-none stroke-current stroke-[1.5]"
    >
      <path d="M12 16V4M6 10l6-6 6 6M5 20h14" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

type DropZoneProps = { kbId: string; parentId: string | null; name: string; className?: string; children: ReactNode };

/**
 * The whole area takes files dropped on it into `parentId`, and only shows itself while files are dragged over it.
 * It takes them before any text editor inside does.
 */
export function FileDropZone({ kbId, parentId, name, className, children }: DropZoneProps) {
  const { t } = useI18n();
  const startUpload = useStartUpload(kbId);
  const [over, setOver] = useState(false);
  return (
    <div
      className={cx("relative", className, over && "rounded-[8px] bg-accent-soft outline-1 outline-ink outline-dashed")}
      onDragOver={(event) => {
        if (!event.dataTransfer.types.includes("Files")) return;
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOver(false);
      }}
      onDropCapture={(event) => {
        if (!event.dataTransfer.files.length) return;
        event.preventDefault();
        event.stopPropagation();
        setOver(false);
        startUpload(Array.from(event.dataTransfer.files), parentId);
      }}
    >
      {over && (
        <p className="pointer-events-none absolute inset-x-0 top-3 m-0 flex items-center justify-center gap-2 text-13 text-text-2">
          <UploadGlyph />
          {t("folder.drop", { name })}
        </p>
      )}
      {children}
    </div>
  );
}

export function UploadList({ kbId }: { kbId: string }) {
  const { t } = useI18n();
  const mine = useUploads().filter((row) => row.kbId === kbId);
  if (mine.length === 0) return null;
  return (
    <section aria-label={t("base.upload.list")} className="mt-3 flex flex-col border-t border-line pt-2">
      <div className="flex h-7 items-center justify-between px-2.5 text-12 text-text-3">
        {t("base.upload.list")}
        <Button variant="quiet" size="sm" onClick={() => clearUploads(kbId)}>
          {t("base.upload.clear")}
        </Button>
      </div>
      <ul className="m-0 flex list-none flex-col gap-1 p-0">
        {mine.map((row) => (
          <li key={row.id} className="flex flex-col gap-0.5 text-12">
            <Upload row={row} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function Upload({ row }: { row: UploadRow }) {
  const { t } = useI18n();
  const retry = useRetryUpload(row.kbId);
  const { name, ext } = splitExt(row.name);
  // A duplicate's Baixar gives the file it matches.
  const download = useDownloadFile(row.nodeId ?? row.duplicate?.node_id ?? "", row.name);
  return (
    <>
      <MediaRow
        kind="file"
        name={name}
        ext={ext}
        progress={row.state === "sending" ? row.percent : undefined}
        failed={row.state === "error"}
        onDownload={() => download.mutate(undefined)}
        onRetry={() => retry(row)}
      />
      {row.state === "duplicate" && row.duplicate && (
        <span className="px-1 text-err">
          {row.duplicate.trashed ? (
            t("base.upload.duplicateTrashed", { path: row.duplicate.path })
          ) : (
            <>
              {t(row.duplicate.history ? "base.upload.duplicateHistory" : "base.upload.duplicate")}{" "}
              <Link to={`/kbs/${row.kbId}/n/${row.duplicate.node_id}`} className="text-err underline">
                {row.duplicate.path}
              </Link>
            </>
          )}
        </span>
      )}
      {row.state === "error" && <span className="px-1 text-err">{row.message}</span>}
    </>
  );
}
