import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { call, invalidate } from "./request";

function refreshKbs(queryClient: QueryClient) {
  return invalidate(queryClient, ["kbs"], ["trash-kbs"], ["favorites"]);
}

export function useKbs(q = "") {
  return useQuery({
    queryKey: ["kbs", q],
    queryFn: () => call(api.GET("/v1/kbs", { params: { query: { q } } })),
  });
}

export function useCreateKb() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, description = "" }: { name: string; description?: string }) =>
      call(api.POST("/v1/kbs", { body: { name, description } })),
    onSuccess: () => refreshKbs(queryClient),
  });
}

export function useUpdateKb() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ kbId, ...body }: { kbId: string; name?: string; description?: string; icon?: string | null }) =>
      call(api.PATCH("/v1/kbs/{kb_id}", { params: { path: { kb_id: kbId } }, body })),
    onSuccess: () => refreshKbs(queryClient),
  });
}

export function useTrashKb() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (kbId: string) => call(api.DELETE("/v1/kbs/{kb_id}", { params: { path: { kb_id: kbId } } })),
    onSuccess: () => refreshKbs(queryClient),
  });
}

export function useTrashedKbs() {
  return useQuery({ queryKey: ["trash-kbs"], queryFn: () => call(api.GET("/v1/kbs/trash")) });
}

export function useRestoreKb() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (kbId: string) =>
      call(api.POST("/v1/kbs/{kb_id}/restore", { params: { path: { kb_id: kbId } } })),
    onSuccess: () => refreshKbs(queryClient),
  });
}
