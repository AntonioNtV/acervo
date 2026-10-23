import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema.gen";
import { call, invalidate, refreshTree, samePath } from "./request";

type Schemas = components["schemas"];

// A favorite shows the node's title, icon and base, and leaves with it for the trash.
const refreshWithFavorites = (queryClient: QueryClient) =>
  Promise.all([refreshTree(queryClient), invalidate(queryClient, ["favorites"])]);

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
    onSuccess: () => Promise.all([refreshTree(queryClient), invalidate(queryClient, ["versions"], ["diff"], ["favorites"])]),
  });
}

export function useDescribeNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ nodeId, description }: { nodeId: string; description: string }) =>
      call(api.PATCH("/v1/nodes/{node_id}", { params: { path: { node_id: nodeId } }, body: { description } })),
    onSuccess: () => refreshTree(queryClient),
  });
}

/** The person's icon (an emoji) or gallery cover of a node; null removes it, a field left out keeps it. */
export function useDecorateNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ nodeId, ...body }: { nodeId: string } & Pick<Schemas["NodeEdit"], "icon" | "cover">) =>
      call(api.PATCH("/v1/nodes/{node_id}", { params: { path: { node_id: nodeId } }, body })),
    onSuccess: () => refreshWithFavorites(queryClient),
  });
}

export function useMoveNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ nodeId, ...body }: { nodeId: string } & Schemas["NodeMove"]) =>
      call(api.POST("/v1/nodes/{node_id}/move", { params: { path: { node_id: nodeId } }, body })),
    onSuccess: () => refreshWithFavorites(queryClient),
  });
}

export function useTrashNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (nodeId: string) =>
      call(api.DELETE("/v1/nodes/{node_id}", { params: { path: { node_id: nodeId } } })),
    onSuccess: () => refreshWithFavorites(queryClient),
  });
}

/** "<título> (cópia)" right after the page, with its text and sub-pages; resolves to the copy. */
export function useDuplicateNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (nodeId: string) =>
      call(api.POST("/v1/nodes/{node_id}/duplicate", { params: { path: { node_id: nodeId } } })),
    onSuccess: () => refreshTree(queryClient),
  });
}

/** A link to the .zip of a page or folder that opens without the key; only its path and query, for the same origin. */
export function useExportNode() {
  return useMutation({
    mutationFn: async (nodeId: string) => {
      const link = await call(api.POST("/v1/nodes/{node_id}/export/link", { params: { path: { node_id: nodeId } } }));
      return samePath(link.url);
    },
  });
}

export function useRestoreNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (nodeId: string) =>
      call(api.POST("/v1/nodes/{node_id}/restore", { params: { path: { node_id: nodeId } } })),
    onSuccess: () => refreshWithFavorites(queryClient),
  });
}
