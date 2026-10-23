import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiHeaders } from "../api/client";
import type { components, paths } from "../api/schema.gen";
import { ApiError, refreshContent, refreshTree } from "./request";

type FileNode = components["schemas"]["FileNodeRead"];

const UPLOAD = "/v1/kbs/{kb_id}/files" satisfies keyof paths;
const REPLACE = "/v1/nodes/{node_id}/file" satisfies keyof paths;

/** `loaded` and `total` in bytes, for one file. */
export type OnProgress = (loaded: number, total: number) => void;

/**
 * A multipart POST of `fields` (a list repeats its field), resolving to the API's JSON answer. XMLHttpRequest, not
 * fetch: only it reports upload progress.
 */
export function send<T>(path: string, fields: Record<string, string | Blob | Blob[] | undefined>, onProgress?: OnProgress) {
  const form = new FormData();
  for (const [name, value] of Object.entries(fields))
    for (const one of Array.isArray(value) ? value : [value]) if (one !== undefined) form.append(name, one);
  return new Promise<T>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", path);
    for (const [name, value] of Object.entries(apiHeaders)) request.setRequestHeader(name, value);
    request.responseType = "json";
    request.upload.onprogress = (event) => onProgress?.(event.loaded, event.total);
    request.onload = () => {
      if (request.status >= 200 && request.status < 300) return resolve(request.response as T);
      reject(new ApiError(request.status, request.response, request.statusText));
    };
    request.onerror = () => reject(new ApiError(0, null, "network error"));
    request.send(form);
  });
}

/** One file into a folder (`parentId` null for the base's root). A duplicate rejects with `duplicate` and its path. */
export function uploadFile(kbId: string, parentId: string | null, file: File, onProgress?: OnProgress) {
  const path = UPLOAD.replace("{kb_id}", encodeURIComponent(kbId));
  return send<FileNode>(path, { file, ...(parentId ? { parent_id: parentId } : {}) }, onProgress);
}

/** New content for a file node; the current one goes to its history. */
export function replaceFile(nodeId: string, file: File, onProgress?: OnProgress) {
  return send<FileNode>(REPLACE.replace("{node_id}", encodeURIComponent(nodeId)), { file }, onProgress);
}

/** Each file into `parentId` on its own request, one promise per file; the tree refreshes once, after the last settles. */
export function useUploadFiles(kbId: string) {
  const queryClient = useQueryClient();
  return (parentId: string | null, files: File[], onProgress: (index: number) => OnProgress) => {
    const sent = files.map((file, i) => uploadFile(kbId, parentId, file, onProgress(i)));
    void Promise.allSettled(sent).then(() => refreshTree(queryClient));
    return sent;
  };
}

export function useReplaceFile(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, onProgress }: { file: File; onProgress?: OnProgress }) =>
      replaceFile(nodeId, file, onProgress),
    onSuccess: () => Promise.all([refreshContent(queryClient, nodeId), refreshTree(queryClient)]),
  });
}
