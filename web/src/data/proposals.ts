import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema.gen";
import { call, invalidate, refreshTree } from "./request";

type Schemas = components["schemas"];
export type Proposal = Schemas["ProposalRead"];
export type ProposalSummary = Schemas["ProposalSummary"];
export type Payload = Proposal["payload"];
export type RejectReason = Schemas["ProposalReject"]["reason"];
export type Placement = Schemas["Placement"];

export const REJECT_REASONS: RejectReason[] = ["wrong_place", "already_there", "wrong_info", "not_worth_keeping"];

/** The proposals waiting in the base, from any conversation or agent, newest first. */
export function usePendingProposals(kbId: string | undefined) {
  return useQuery({
    queryKey: ["proposals", kbId ?? ""],
    enabled: Boolean(kbId),
    queryFn: () =>
      call(api.GET("/v1/kbs/{kb_id}/proposals", { params: { path: { kb_id: kbId ?? "" }, query: { status: "pending" } } })),
  });
}

/** What the person (or the stream) learned about a proposal: kept for the thread, and the base follows it. */
export function settleProposal(queryClient: QueryClient, proposal: Proposal) {
  queryClient.setQueryData<Record<string, Proposal>>(["proposal-states"], (known) => ({ ...known, [proposal.id]: proposal }));
  const refreshes = [invalidate(queryClient, ["proposals", proposal.kb_id])];
  if (proposal.status === "applied") refreshes.push(refreshTree(queryClient), invalidate(queryClient, ["versions"], ["diff"]));
  return Promise.all(refreshes);
}

/** Every proposal state seen in this session, by id: the thread draws the newest one it knows. */
export function useProposalStates() {
  return useQuery<Record<string, Proposal>>({
    queryKey: ["proposal-states"],
    queryFn: () => ({}),
    staleTime: Infinity,
    gcTime: Infinity,
  });
}

/** The newer of two states of one proposal: what this session was told, or what the API listed. */
function newest<A extends Proposal | ProposalSummary>(known: Proposal | undefined, listed: A): A | Proposal {
  return known && known.updated_at >= listed.updated_at ? known : listed;
}

/** A proposal as it stands now, after whatever the stream or an action told this session. */
export function useLatestProposal<A extends Proposal | ProposalSummary>(proposal: A): A | Proposal {
  return newest(useProposalStates().data?.[proposal.id], proposal);
}

function useProposalAction<T>(action: (proposalId: string, input: T) => Promise<Proposal>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: T }) => action(id, input),
    onSuccess: (proposal) => settleProposal(queryClient, proposal),
  });
}

const path = (proposalId: string) => ({ params: { path: { proposal_id: proposalId } } });

export const useAcceptProposal = () =>
  useProposalAction<void>((id) => call(api.POST("/v1/proposals/{proposal_id}/accept", path(id))));

export const useRejectProposal = () =>
  useProposalAction<RejectReason>((id, reason) =>
    call(api.POST("/v1/proposals/{proposal_id}/reject", { ...path(id), body: { reason } })),
  );

export const useEditProposal = () =>
  useProposalAction<Payload>((id, body) => call(api.PATCH("/v1/proposals/{proposal_id}", { ...path(id), body })));

export const useOtherPlace = () =>
  useProposalAction<void>((id) => call(api.POST("/v1/proposals/{proposal_id}/other-place", path(id))));

/** Resolves to the new `undo` proposal, applied at once when its agent is in auto mode. */
export const useUndoProposal = () =>
  useProposalAction<void>((id) => call(api.POST("/v1/proposals/{proposal_id}/undo", path(id))));

/** Both the edit and the accept, as "Guardar as duas com nota" and choosing a place do. */
export function useEditAndAccept() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, input }: { id: string; input: Payload }) => {
      await call(api.PATCH("/v1/proposals/{proposal_id}", { ...path(id), body: input }));
      return call(api.POST("/v1/proposals/{proposal_id}/accept", path(id)));
    },
    onSuccess: (proposal) => settleProposal(queryClient, proposal),
  });
}
