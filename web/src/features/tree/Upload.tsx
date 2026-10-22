import { useRef, useSyncExternalStore } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../../api/queries";
import { useUploadFile } from "../../api/upload";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
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
  const upload = useUploadFile(kbId);
  const errorText = useTreeErrorText();
  return (files: Iterable<File>, parentId: string | null) => {
    for (const file of files) {
      const id = nextId++;
      update([...rows, { id, kbId, name: file.name, percent: 0, state: "sending" }]);
      upload
        .mutateAsync({
          parentId,
          file,
          onProgress: (loaded, total) => patch(id, { percent: total ? Math.round((loaded / total) * 100) : 0 }),
        })
        .then(
          () => patch(id, { state: "done", percent: 100 }),
          (error: unknown) => {
            const detail = error instanceof ApiError ? error.body.detail : null;
            if (detail && "node_id" in detail) {
              patch(id, { state: "duplicate", duplicate: detail as Row["duplicate"] });
            } else {
              patch(id, { state: "error", message: errorText(error) });
            }
          },
        );
    }
  };
}

export function UploadButton({ kbId, parentId }: { kbId: string; parentId: string | null }) {
  const { t } = useI18n();
  const start = useStartUpload(kbId);
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <Button onClick={() => input.current?.click()}>{t("tree.upload")}</Button>
      <input
        ref={input}
        type="file"
        multiple
        hidden
        aria-label={t("tree.upload")}
        onChange={(event) => {
          start(Array.from(event.target.files ?? []), parentId);
          event.target.value = "";
        }}
      />
    </>
  );
}

export function UploadList({ kbId }: { kbId: string }) {
  const { t } = useI18n();
  const all = useSyncExternalStore(subscribe, () => rows);
  const mine = all.filter((row) => row.kbId === kbId);
  if (mine.length === 0) return null;
  return (
    <section aria-label={t("tree.upload.list")} className="mt-3 flex flex-col border-t border-line pt-2">
      <div className="flex h-7 items-center justify-between px-2.5 text-12 text-text-3">
        {t("tree.upload.list")}
        <Button variant="quiet" size="sm" onClick={() => clearUploads(kbId)}>
          {t("tree.upload.clear")}
        </Button>
      </div>
      <ul className="m-0 flex list-none flex-col p-0">
        {mine.map((row) => (
          <li key={row.id} className="flex flex-col px-2.5 py-1 text-12">
            <span className="flex justify-between gap-2">
              <span className="truncate text-text-2">{row.name}</span>
              {row.state === "sending" && <span className="text-text-3 tabular-nums">{row.percent}%</span>}
              {row.state === "done" && <span className="text-text-3">{t("tree.upload.done")}</span>}
            </span>
            {row.state === "duplicate" && row.duplicate && (
              <span className="text-err">
                {row.duplicate.trashed ? (
                  t("tree.upload.duplicateTrashed", { path: row.duplicate.path })
                ) : (
                  <>
                    {t(row.duplicate.history ? "tree.upload.duplicateHistory" : "tree.upload.duplicate")}{" "}
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
