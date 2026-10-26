import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, apiHeaders } from "../api/client";
import type { paths } from "../api/schema.gen";
import { call, refreshContent, samePath } from "./request";

const RAW = "/v1/files/{node_id}/raw" satisfies keyof paths;

/** Where pdf.js reads the original file by range requests, and the headers it sends with each. */
export function rawFileSource(nodeId: string): { url: string; httpHeaders: Record<string, string> } {
  return { url: RAW.replace("{node_id}", encodeURIComponent(nodeId)), httpHeaders: apiHeaders };
}

/** A link that opens the bytes without the key for 60 s; only its path and query, so it goes through the same origin. */
async function fileLink(nodeId: string, versionId?: string): Promise<string> {
  const { url } = await call(
    api.POST("/v1/files/{node_id}/link", {
      params: { path: { node_id: nodeId }, query: versionId ? { version_id: versionId } : {} },
    }),
  );
  return samePath(url);
}

/** A signed link for an `<img>`, which cannot send the key; a new one when the content changes. */
export function useRawFileUrl(nodeId: string, sha256: string | undefined) {
  return useQuery({
    queryKey: ["link", nodeId, sha256],
    queryFn: () => fileLink(nodeId),
    // The link expires in 60 s: never refetched while shown, never reused after.
    staleTime: Infinity,
    gcTime: 0,
  });
}

/** "Baixar": the browser streams the signed link to disk under `filename`. */
export function useDownloadFile(nodeId: string, filename: string) {
  return useMutation({
    mutationFn: (versionId?: string) => fileLink(nodeId, versionId),
    onSuccess: (href) => {
      const link = document.createElement("a");
      link.href = href;
      link.download = filename;
      link.click();
    },
  });
}

/** "Abrir": a new tab on a fresh signed link, since the one an `<img>` got may have expired. */
export function useOpenFile(nodeId: string) {
  return useMutation({
    mutationFn: () => fileLink(nodeId),
    onSuccess: (href) => window.open(href, "_blank", "noopener"),
  });
}

/** A file's older contents (its current one is the node), newest first. */
export function useFileVersions(nodeId: string) {
  return useQuery({
    queryKey: ["versions", nodeId],
    queryFn: () => call(api.GET("/v1/files/{node_id}/versions", { params: { path: { node_id: nodeId } } })),
  });
}

export function useRestoreFileVersion(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (versionId: string) =>
      call(
        api.POST("/v1/files/{node_id}/versions/{version_id}/restore", {
          params: { path: { node_id: nodeId, version_id: versionId } },
        }),
      ),
    onSuccess: () => refreshContent(queryClient, nodeId),
  });
}
