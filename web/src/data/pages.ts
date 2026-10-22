import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema.gen";
import { call, invalidate, refreshContent } from "./request";

/** The key the API gives each `[[…]]` target in `page.links`: whitespace collapsed, lowercased. */
export function normalizeLinkTarget(title: string): string {
  return title.split(/\s+/).filter(Boolean).join(" ").toLowerCase();
}

/** A `stale_page` error rejects with an `ApiError` whose `details` is a `StalePage`. */
export function useSavePage(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ force = false, ...body }: { markdown: string; base_version_id: string; force?: boolean }) =>
      call(api.PUT("/v1/pages/{node_id}", { params: { path: { node_id: nodeId } }, body: { ...body, force } })),
    onSuccess: () => refreshContent(queryClient, nodeId),
  });
}

/** The autosave; it leaves the node's query alone so the editor is not reset under the person. */
export function usePutDraft(nodeId: string) {
  return useMutation({
    mutationFn: (body: components["schemas"]["DraftPut"]) =>
      call(api.PUT("/v1/pages/{node_id}/draft", { params: { path: { node_id: nodeId } }, body })),
  });
}

export function useDiscardDraft(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => call(api.DELETE("/v1/pages/{node_id}/draft", { params: { path: { node_id: nodeId } } })),
    onSuccess: () => invalidate(queryClient, ["node", nodeId]),
  });
}

/** A page's versions, newest first. */
export function usePageVersions(nodeId: string) {
  return useQuery({
    queryKey: ["versions", nodeId],
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
