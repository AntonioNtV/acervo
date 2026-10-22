import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { components, paths } from "./schema.gen";

type Schemas = components["schemas"];
export type ErrorResponse = Schemas["ErrorResponse"];
export type KbSummary = Schemas["KbSummaryResponse"];
export type Kb = Schemas["KbResponse"];
export type TreeNode = Schemas["TreeNodeResponse"];
export type NodeDetail = Schemas["NodeDetailResponse"];
export type SearchHit = Schemas["SearchHitResponse"];
export type TrashItem = Schemas["TrashItemResponse"];
export type Version = Schemas["VersionResponse"];
export type DiffLine = Schemas["DiffLineResponse"];
export type StalePage = Schemas["StalePageDetail"];

export const apiBaseUrl: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** Any answer outside 2xx; `status` 0 when the request never reached the API. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: ErrorResponse,
  ) {
    super(body.message);
  }
}

async function call<T>(request: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await request;
  if (!response.ok) {
    const body = (error as ErrorResponse | undefined) ?? { error: "HttpError", message: response.statusText };
    throw new ApiError(response.status, body);
  }
  return data as T;
}

/** The key the API gives each `[[…]]` target in `page.links`: whitespace collapsed, lowercased. */
export function normalizeLinkTarget(title: string): string {
  return title.split(/\s+/).filter(Boolean).join(" ").toLowerCase();
}

const RAW = "/files/{node_id}/raw" satisfies keyof paths;

/** The original bytes, for the PDF viewer, an image and "Baixar"; `Range` is honored. */
export function rawFileUrl(nodeId: string, versionId?: string): string {
  const url = `${apiBaseUrl}${RAW.replace("{node_id}", encodeURIComponent(nodeId))}`;
  return versionId ? `${url}?version_id=${encodeURIComponent(versionId)}` : url;
}

const keys = {
  kbs: (q: string) => ["kbs", q] as const,
  trashedKbs: ["trash-kbs"] as const,
  children: (kbId: string, parentId: string | null) => ["children", kbId, parentId] as const,
  search: (kbId: string, q: string) => ["search", kbId, q] as const,
  trash: (kbId: string) => ["trash", kbId] as const,
  node: (nodeId: string) => ["node", nodeId] as const,
  versions: (nodeId: string) => ["versions", nodeId] as const,
  diff: (nodeId: string, versionId: string) => ["diff", nodeId, versionId] as const,
};

function invalidate(queryClient: QueryClient, ...prefixes: string[][]) {
  return Promise.all(prefixes.map((queryKey) => queryClient.invalidateQueries({ queryKey })));
}

/** After anything that changes where nodes are or what they are called; a page rename rewrites other pages too. */
export function refreshTree(queryClient: QueryClient) {
  return invalidate(queryClient, ["children"], ["search"], ["trash"], ["node"], ["kbs"]);
}

/** After a node's content changed: a page version, a replaced or restored file. */
export function refreshContent(queryClient: QueryClient, nodeId: string) {
  return invalidate(queryClient, ["node", nodeId], ["versions", nodeId], ["diff", nodeId], ["kbs"]);
}

function refreshKbs(queryClient: QueryClient) {
  return invalidate(queryClient, ["kbs"], ["trash-kbs"]);
}

// Bases

export function useKbs(q = "") {
  return useQuery({
    queryKey: keys.kbs(q),
    queryFn: () => call(api.GET("/kbs", { params: { query: { q } } })),
  });
}

export function useCreateKb() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, description = "" }: { name: string; description?: string }) =>
      call(api.POST("/kbs", { body: { name, description } })),
    onSuccess: () => refreshKbs(queryClient),
  });
}

export function useUpdateKb() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ kbId, ...body }: { kbId: string; name?: string; description?: string }) =>
      call(api.PATCH("/kbs/{kb_id}", { params: { path: { kb_id: kbId } }, body })),
    onSuccess: () => refreshKbs(queryClient),
  });
}

export function useTrashKb() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (kbId: string) => call(api.DELETE("/kbs/{kb_id}", { params: { path: { kb_id: kbId } } })),
    onSuccess: () => refreshKbs(queryClient),
  });
}

export function useTrashedKbs() {
  return useQuery({ queryKey: keys.trashedKbs, queryFn: () => call(api.GET("/trash/kbs")) });
}

export function useRestoreKb() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (kbId: string) => call(api.POST("/kbs/{kb_id}/restore", { params: { path: { kb_id: kbId } } })),
    onSuccess: () => refreshKbs(queryClient),
  });
}

// The tree

export function useChildren(kbId: string, parentId: string | null = null) {
  return useQuery({
    queryKey: keys.children(kbId, parentId),
    queryFn: () =>
      call(
        api.GET("/kbs/{kb_id}/children", {
          params: { path: { kb_id: kbId }, query: parentId ? { parent_id: parentId } : {} },
        }),
      ),
  });
}

export function useSearch(kbId: string, q: string) {
  return useQuery({
    queryKey: keys.search(kbId, q),
    queryFn: () => call(api.GET("/kbs/{kb_id}/search", { params: { path: { kb_id: kbId }, query: { q } } })),
    enabled: q.trim() !== "",
  });
}

export function useKbTrash(kbId: string) {
  return useQuery({
    queryKey: keys.trash(kbId),
    queryFn: () => call(api.GET("/kbs/{kb_id}/trash", { params: { path: { kb_id: kbId } } })),
  });
}

export function useCreateNode(kbId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["CreateNodeRequest"]) =>
      call(api.POST("/kbs/{kb_id}/nodes", { params: { path: { kb_id: kbId } }, body })),
    onSuccess: () => refreshTree(queryClient),
  });
}

export function useRenameNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ nodeId, title }: { nodeId: string; title: string }) =>
      call(api.PATCH("/nodes/{node_id}", { params: { path: { node_id: nodeId } }, body: { title } })),
    onSuccess: () => Promise.all([refreshTree(queryClient), invalidate(queryClient, ["versions"], ["diff"])]),
  });
}

export function useMoveNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ nodeId, ...body }: { nodeId: string } & Schemas["MoveNodeRequest"]) =>
      call(api.POST("/nodes/{node_id}/move", { params: { path: { node_id: nodeId } }, body })),
    onSuccess: () => refreshTree(queryClient),
  });
}

export function useTrashNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (nodeId: string) => call(api.DELETE("/nodes/{node_id}", { params: { path: { node_id: nodeId } } })),
    onSuccess: () => refreshTree(queryClient),
  });
}

export function useRestoreNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (nodeId: string) =>
      call(api.POST("/nodes/{node_id}/restore", { params: { path: { node_id: nodeId } } })),
    onSuccess: () => refreshTree(queryClient),
  });
}

// Pages and files

export function useNode(nodeId: string) {
  return useQuery({
    queryKey: keys.node(nodeId),
    queryFn: () => call(api.GET("/nodes/{node_id}", { params: { path: { node_id: nodeId } } })),
  });
}

/** A 409 rejects with an `ApiError` whose `body.detail` is a `StalePage`. */
export function useSavePage(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ force = false, ...body }: { markdown: string; base_version_id: string; force?: boolean }) =>
      call(api.PUT("/nodes/{node_id}", { params: { path: { node_id: nodeId } }, body: { ...body, force } })),
    onSuccess: () => refreshContent(queryClient, nodeId),
  });
}

/** The autosave; it leaves the node's query alone so the editor is not reset under the person. */
export function usePutDraft(nodeId: string) {
  return useMutation({
    mutationFn: (body: Schemas["PutDraftRequest"]) =>
      call(api.PUT("/nodes/{node_id}/draft", { params: { path: { node_id: nodeId } }, body })),
  });
}

export function useDiscardDraft(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => call(api.DELETE("/nodes/{node_id}/draft", { params: { path: { node_id: nodeId } } })),
    onSuccess: () => invalidate(queryClient, ["node", nodeId]),
  });
}

/** A page's versions, or a file's older contents (its current one is the node), newest first. */
export function useVersions(nodeId: string) {
  return useQuery({
    queryKey: keys.versions(nodeId),
    queryFn: () => call(api.GET("/nodes/{node_id}/versions", { params: { path: { node_id: nodeId } } })),
  });
}

export function useVersionDiff(nodeId: string, versionId: string | null) {
  return useQuery({
    queryKey: keys.diff(nodeId, versionId ?? ""),
    queryFn: () =>
      call(
        api.GET("/nodes/{node_id}/versions/{version_id}/diff", {
          params: { path: { node_id: nodeId, version_id: versionId ?? "" } },
        }),
      ),
    enabled: versionId !== null,
  });
}

export function useRestoreVersion(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (versionId: string) =>
      call(
        api.POST("/nodes/{node_id}/versions/{version_id}/restore", {
          params: { path: { node_id: nodeId, version_id: versionId } },
        }),
      ),
    onSuccess: () => refreshContent(queryClient, nodeId),
  });
}
