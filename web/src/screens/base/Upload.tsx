import { useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../../data/request";
import { useUploadFiles } from "../../data/upload";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { cx } from "../../ui/cx";
import { useTreeErrorText } from "./names";

type Row = {
  id: number;
  kbId: string;
  name: string;
  percent: number;
  state: "sending" | "done" | "duplicate" | "error";
  message?: string;
  duplicate?: { node_id: string; path: string; trashed: boolean; history?: boolean };
};

// Module state, so a drop on the tree and the folder view's button feed the same list in the tree column.
let rows: Row[] = [];
let nextId = 0;
const listeners = new Set<() => void>();

function update(next: Row[]) {
  rows = next;
  for (const listener of listeners) listener();
}

function patch(id: number, change: Partial<Row>) {
  update(rows.map((row) => (row.id === id ? { ...row, ...change } : row)));
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function clearUploads(kbId: string) {
  update(rows.filter((row) => row.kbId !== kbId || row.state === "sending"));
}

/** Sends each file into `parentId` (null for the root), one row of progress per file. */
export function useStartUpload(kbId: string) {
  const upload = useUploadFiles(kbId);
  const errorText = useTreeErrorText();
  return (files: Iterable<File>, parentId: string | null) => {
    const list = Array.from(files);
    const ids = list.map((file) => {
      const id = nextId++;
      update([...rows, { id, kbId, name: file.name, percent: 0, state: "sending" }]);
      return id;
    });
    const progress = (i: number) => (loaded: number, total: number) =>
      patch(ids[i]!, { percent: total ? Math.round((loaded / total) * 100) : 0 });
    upload(parentId, list, progress).forEach((sent, i) =>
      sent.then(
        () => patch(ids[i]!, { state: "done", percent: 100 }),
        (error: unknown) => {
          if (error instanceof ApiError && error.code === "duplicate") {
            patch(ids[i]!, { state: "duplicate", duplicate: error.details as Row["duplicate"] });
          } else {
            patch(ids[i]!, { state: "error", message: errorText(error) });
          }
        },
      ),
    );
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
  const all = useSyncExternalStore(subscribe, () => rows);
  const mine = all.filter((row) => row.kbId === kbId);
  if (mine.length === 0) return null;
  return (
    <section aria-label={t("base.upload.list")} className="mt-3 flex flex-col border-t border-line pt-2">
      <div className="flex h-7 items-center justify-between px-2.5 text-12 text-text-3">
        {t("base.upload.list")}
        <Button variant="quiet" size="sm" onClick={() => clearUploads(kbId)}>
          {t("base.upload.clear")}
        </Button>
      </div>
      <ul className="m-0 flex list-none flex-col p-0">
        {mine.map((row) => (
          <li key={row.id} className="flex flex-col px-2.5 py-1 text-12">
            <span className="flex justify-between gap-2">
              <span className="truncate text-text-2">{row.name}</span>
              {row.state === "sending" && <span className="text-text-3 tabular-nums">{row.percent}%</span>}
              {row.state === "done" && <span className="text-text-3">{t("base.upload.done")}</span>}
            </span>
            {row.state === "duplicate" && row.duplicate && (
              <span className="text-err">
                {row.duplicate.trashed ? (
                  t("base.upload.duplicateTrashed", { path: row.duplicate.path })
                ) : (
                  <>
                    {t(row.duplicate.history ? "base.upload.duplicateHistory" : "base.upload.duplicate")}{" "}
                    <Link to={`/kbs/${kbId}/n/${row.duplicate.node_id}`} className="text-err underline">
                      {row.duplicate.path}
                    </Link>
                  </>
                )}
              </span>
            )}
            {row.state === "error" && <span className="text-err">{row.message}</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}
