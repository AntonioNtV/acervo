import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema.gen";
import { call, invalidate, refreshTree } from "./request";

type Schemas = components["schemas"];

export function useChildren(kbId: string, parentId: string | null = null, enabled = true) {
  return useQuery({
    queryKey: ["children", kbId, parentId],
    enabled,
    queryFn: () =>
      call(
        api.GET("/v1/kbs/{kb_id}/children", {
          params: { path: { kb_id: kbId }, query: parentId ? { parent_id: parentId } : {} },
        }),
      ),
  });
}

export function useSearch(kbId: string, q: string) {
  return useQuery({
    queryKey: ["search", kbId, q],
    queryFn: () => call(api.GET("/v1/kbs/{kb_id}/search", { params: { path: { kb_id: kbId }, query: { q } } })),
    enabled: q.trim() !== "",
  });
}

export function useKbTrash(kbId: string) {
  return useQuery({
    queryKey: ["trash", kbId],
    queryFn: () => call(api.GET("/v1/kbs/{kb_id}/trash", { params: { path: { kb_id: kbId } } })),
  });
}

/** A folder, page or file with its path, its page and file parts and its version count. */
export function useNode(nodeId: string, enabled = true) {
  return useQuery({
    queryKey: ["node", nodeId],
    enabled,
    queryFn: () => call(api.GET("/v1/nodes/{node_id}", { params: { path: { node_id: nodeId } } })),
  });
}

export function useCreateNode(kbId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["NodeAdd"]) =>
      call(api.POST("/v1/kbs/{kb_id}/nodes", { params: { path: { kb_id: kbId } }, body })),
    onSuccess: () => refreshTree(queryClient),
  });
}

export function useRenameNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ nodeId, title }: { nodeId: string; title: string }) =>
      call(api.PATCH("/v1/nodes/{node_id}", { params: { path: { node_id: nodeId } }, body: { title } })),
    onSuccess: () => Promise.all([refreshTree(queryClient), invalidate(queryClient, ["versions"], ["diff"])]),
  });
}

export function useMoveNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ nodeId, ...body }: { nodeId: string } & Schemas["NodeMove"]) =>
      call(api.POST("/v1/nodes/{node_id}/move", { params: { path: { node_id: nodeId } }, body })),
    onSuccess: () => refreshTree(queryClient),
  });
}

export function useTrashNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (nodeId: string) =>
      call(api.DELETE("/v1/nodes/{node_id}", { params: { path: { node_id: nodeId } } })),
    onSuccess: () => refreshTree(queryClient),
  });
}

export function useRestoreNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (nodeId: string) =>
      call(api.POST("/v1/nodes/{node_id}/restore", { params: { path: { node_id: nodeId } } })),
    onSuccess: () => refreshTree(queryClient),
  });
}
