import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, apiHeaders } from "../api/client";
import type { paths } from "../api/schema.gen";
import { call, refreshContent } from "./request";

const RAW = "/v1/files/{node_id}/raw" satisfies keyof paths;

/** Where pdf.js reads the original file by range requests, and the headers it sends with each. */
export function rawFileSource(nodeId: string): { url: string; httpHeaders: Record<string, string> } {
  return { url: RAW.replace("{node_id}", encodeURIComponent(nodeId)), httpHeaders: apiHeaders };
}

function fetchRaw(nodeId: string, versionId?: string): Promise<Blob> {
  return call(
    api.GET(RAW, {
      params: { path: { node_id: nodeId }, query: versionId ? { version_id: versionId } : {} },
      parseAs: "blob",
    }),
  );
}

/** A blob URL of the original file, for an `<img>`, which cannot send the key; null until it has arrived. */
export function useRawFileUrl(nodeId: string, sha256: string | undefined) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    let made: string | null = null;
    fetchRaw(nodeId).then(
      (blob) => {
        if (!live) return;
        made = URL.createObjectURL(blob);
        setUrl(made);
      },
      () => {},
    );
    return () => {
      live = false;
      if (made) URL.revokeObjectURL(made);
    };
  }, [nodeId, sha256]);
  return url;
}

/** "Baixar": fetches the bytes with the key and saves them under `filename`. */
export async function downloadFile(nodeId: string, filename: string, versionId?: string) {
  const url = URL.createObjectURL(await fetchRaw(nodeId, versionId));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  // Revoking in the same task can cancel the download in some browsers.
  setTimeout(() => URL.revokeObjectURL(url), 0);
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
