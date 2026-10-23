import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { call, invalidate } from "./request";

/** The person's favorites across bases, in their order; trashed nodes and bases leave it. */
export function useFavorites() {
  return useQuery({ queryKey: ["favorites"], queryFn: () => call(api.GET("/v1/favorites")) });
}

/**
 * Puts a page or folder in the favorites, last or just before `before_id` (a favorite already there moves), or takes
 * it out. The node's `favorite` flag changes with it.
 */
export function useFavorite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ nodeId, favorite, before_id = null }: { nodeId: string; favorite: boolean; before_id?: string | null }) => {
      const params = { path: { node_id: nodeId } };
      return favorite
        ? call(api.PUT("/v1/nodes/{node_id}/favorite", { params, body: { before_id } }))
        : call(api.DELETE("/v1/nodes/{node_id}/favorite", { params }));
    },
    onSuccess: () => invalidate(queryClient, ["favorites"], ["node"], ["children"]),
  });
}
