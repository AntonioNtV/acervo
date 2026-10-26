import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { api } from "../api/client";
import { call, invalidate, refreshContent } from "./request";

/** The key the API gives each `[[…]]` target in `page.links`: whitespace collapsed, lowercased. */
export function normalizeLinkTarget(title: string): string {
  return title.split(/\s+/).filter(Boolean).join(" ").toLowerCase();
}

/** The `details` of a `stale_page` error: the newest text and its revision. */
export type StaleText = { markdown: string; revision: number };

/**
 * The autosave of the working text. A `stale_page` rejects with an `ApiError` whose `details` is a `StaleText`.
 * The request goes out as soon as the function is called, so one sent right after it goes out after it. It refreshes
 * the node so new `[[…]]` links resolve, without waiting for that; the editor only reads the text it opened with.
 * `keepalive` lets the request outlive a closing tab; the browser refuses it for a body over 64 KB.
 */
export function useSavePageText(nodeId: string) {
  const queryClient = useQueryClient();
  return useCallback(
    async (body: { markdown: string; revision: number }, keepalive = false) => {
      const path = { node_id: nodeId };
      const saved = await call(api.PUT("/v1/pages/{node_id}/text", { params: { path }, body, keepalive }));
      void invalidate(queryClient, ["node", nodeId]);
      return saved;
    },
    [queryClient, nodeId],
  );
}

/** The person left the page: its working text becomes a version. Sent so it outlives a closing tab. */
export function leavePage(nodeId: string): Promise<unknown> {
  return call(api.POST("/v1/pages/{node_id}/leave", { params: { path: { node_id: nodeId } }, keepalive: true })).catch(
    () => undefined,
  );
}

/** A page's versions, newest first. Reading them cuts the working text as a version, so only an open history asks. */
export function usePageVersions(nodeId: string, enabled = true) {
  return useQuery({
    queryKey: ["versions", nodeId],
    enabled,
    queryFn: () => call(api.GET("/v1/pages/{node_id}/versions", { params: { path: { node_id: nodeId } } })),
  });
}

export function usePageVersionDiff(nodeId: string, versionId: string | null) {
  return useQuery({
    queryKey: ["diff", nodeId, versionId ?? ""],
    queryFn: () =>
      call(
        api.GET("/v1/pages/{node_id}/versions/{version_id}/diff", {
          params: { path: { node_id: nodeId, version_id: versionId ?? "" } },
        }),
      ),
    enabled: versionId !== null,
  });
}

/** The pages of the base with a `[[…]]` link to this one, each with the line holding it. */
export function usePageMentions(nodeId: string) {
  return useQuery({
    queryKey: ["mentions", nodeId],
    queryFn: () => call(api.GET("/v1/pages/{node_id}/mentions", { params: { path: { node_id: nodeId } } })),
  });
}

/** Follows the page for the daily digest, or stops; the page's `following` changes with it. */
export function useFollowPage(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (follow: boolean) => {
      const params = { path: { node_id: nodeId } };
      return follow
        ? call(api.PUT("/v1/pages/{node_id}/follow", { params }))
        : call(api.DELETE("/v1/pages/{node_id}/follow", { params }));
    },
    onSuccess: () => invalidate(queryClient, ["node", nodeId]),
  });
}

/** Resolves to the page as it is after the restore: its text and the revision to save from. */
export function useRestorePageVersion(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (versionId: string) =>
      call(
        api.POST("/v1/pages/{node_id}/versions/{version_id}/restore", {
          params: { path: { node_id: nodeId, version_id: versionId } },
        }),
      ),
    onSuccess: () => refreshContent(queryClient, nodeId),
  });
}
