import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema.gen";
import { call, invalidate } from "./request";

export type Agent = components["schemas"]["AgentRead"];
export type AgentMode = Agent["mode"];

/** Where an agent connects: the API's own origin, which the dev server does not proxy for `/mcp`. */
export const mcpUrl = () => `${import.meta.env.VITE_API_URL || window.location.origin}/mcp`;

/** The base's built-in chat first, then the agents connected to it, revoked ones included. */
export function useAgents(kbId: string) {
  return useQuery({
    queryKey: ["agents", kbId],
    queryFn: () => call(api.GET("/v1/kbs/{kb_id}/agents", { params: { path: { kb_id: kbId } } })),
  });
}

/** Resolves with the agent and its token, which the API gives this once. */
export function useConnectAgent(kbId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) =>
      call(api.POST("/v1/kbs/{kb_id}/agents", { params: { path: { kb_id: kbId } }, body: { name, mode: "ask" } })),
    onSuccess: () => invalidate(queryClient, ["agents", kbId]),
  });
}

export function useSetAgentMode(kbId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ agentId, mode }: { agentId: string; mode: AgentMode }) =>
      call(api.PATCH("/v1/agents/{agent_id}", { params: { path: { agent_id: agentId } }, body: { mode } })),
    onSuccess: () => invalidate(queryClient, ["agents", kbId]),
  });
}

export function useRevokeAgent(kbId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (agentId: string) =>
      call(api.DELETE("/v1/agents/{agent_id}", { params: { path: { agent_id: agentId } } })),
    onSuccess: () => invalidate(queryClient, ["agents", kbId]),
  });
}
