import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiBaseUrl } from "./client";
import { ApiError, refreshContent, refreshTree, type NodeDetail } from "./queries";
import type { components, paths } from "./schema.gen";

type UploadField = keyof components["schemas"]["Body_upload_file_kbs__kb_id__files_post"];

const UPLOAD = "/kbs/{kb_id}/files" satisfies keyof paths;
const REPLACE = "/nodes/{node_id}/file" satisfies keyof paths;

/** `loaded` and `total` in bytes, for one file. */
export type OnProgress = (loaded: number, total: number) => void;

// XMLHttpRequest, not fetch: only it reports upload progress.
function send(path: string, fields: Partial<Record<UploadField, string | Blob>>, onProgress?: OnProgress) {
  const form = new FormData();
  for (const [name, value] of Object.entries(fields)) if (value !== undefined) form.append(name, value);
  return new Promise<NodeDetail>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${apiBaseUrl}${path}`);
    request.responseType = "json";
    request.upload.onprogress = (event) => onProgress?.(event.loaded, event.total);
    request.onload = () => {
      if (request.status >= 200 && request.status < 300) return resolve(request.response as NodeDetail);
      reject(new ApiError(request.status, request.response, request.statusText));
    };
    request.onerror = () => reject(new ApiError(0, null, "network error"));
    request.send(form);
  });
}

/** One file into a folder (`parentId` null for the base's root). A duplicate rejects with 409 and its path. */
export function uploadFile(kbId: string, parentId: string | null, file: File, onProgress?: OnProgress) {
  const path = UPLOAD.replace("{kb_id}", encodeURIComponent(kbId));
  return send(path, { file, ...(parentId ? { parent_id: parentId } : {}) }, onProgress);
}

/** New content for a file node; the current one goes to its history. */
export function replaceFile(nodeId: string, file: File, onProgress?: OnProgress) {
  return send(REPLACE.replace("{node_id}", encodeURIComponent(nodeId)), { file }, onProgress);
}

export function useUploadFile(kbId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ parentId, file, onProgress }: { parentId: string | null; file: File; onProgress?: OnProgress }) =>
      uploadFile(kbId, parentId, file, onProgress),
    onSuccess: () => refreshTree(queryClient),
  });
}

export function useReplaceFile(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, onProgress }: { file: File; onProgress?: OnProgress }) =>
      replaceFile(nodeId, file, onProgress),
    onSuccess: () => Promise.all([refreshContent(queryClient, nodeId), refreshTree(queryClient)]),
  });
}
