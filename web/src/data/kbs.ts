import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { api, type KbSummary } from "../api/client";
import { useCurrentOrganization } from "./organizations";
import { call, invalidate } from "./request";

function refreshKbs(queryClient: QueryClient) {
  return invalidate(queryClient, ["kbs"], ["trash-kbs"], ["favorites"]);
}

/** The bases of the current organization; the Pessoal's include those shared with the person, with `shared_by`. */
export function useKbs(q = "") {
  const organization_id = useCurrentOrganization().id;
  return useQuery({
    queryKey: ["kbs", organization_id ?? null, q],
    queryFn: () => call(api.GET("/v1/kbs", { params: { query: { q, organization_id } } })),
  });
}

/** Creates the base in the current organization. */
export function useCreateKb() {
  const queryClient = useQueryClient();
  const organization_id = useCurrentOrganization().id;
  return useMutation({
    mutationFn: ({ name, description = "" }: { name: string; description?: string }) =>
      call(api.POST("/v1/kbs", { body: { name, description, organization_id } })),
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

/** A base's emoji from its menu: whether the picker is open, and what it picks or removes. */
export function useKbIcon(kb: KbSummary) {
  const update = useUpdateKb();
  const [picking, setPicking] = useState(false);
  const close = useCallback(() => setPicking(false), []);
  const setIcon = (icon: string | null) => {
    setPicking(false);
    update.mutate({ kbId: kb.id, icon });
  };
  return {
    picking,
    open: () => setPicking(true),
    close,
    pick: setIcon,
    remove: kb.icon ? () => setIcon(null) : undefined,
  };
}

export function useTrashKb() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (kbId: string) => call(api.DELETE("/v1/kbs/{kb_id}", { params: { path: { kb_id: kbId } } })),
    onSuccess: () => refreshKbs(queryClient),
  });
}

export function useTrashedKbs() {
  const organization_id = useCurrentOrganization().id;
  return useQuery({
    queryKey: ["trash-kbs", organization_id ?? null],
    queryFn: () => call(api.GET("/v1/kbs/trash", { params: { query: { organization_id } } })),
  });
}

export function useRestoreKb() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (kbId: string) =>
      call(api.POST("/v1/kbs/{kb_id}/restore", { params: { path: { kb_id: kbId } } })),
    onSuccess: () => refreshKbs(queryClient),
  });
}
