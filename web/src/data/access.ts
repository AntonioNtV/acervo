import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema.gen";
import { useKbs } from "./kbs";
import { call, invalidate } from "./request";

export type BaseRole = components["schemas"]["BaseMemberChange"]["role"];
export type GeneralAccess = components["schemas"]["BaseAccess"]["general_access"];
export type BaseMember = components["schemas"]["MemberRead"];
export type Invite = components["schemas"]["InviteRead"];

/**
 * The person's role in a base, and what it lets the screens offer. Until the bases load the role is unknown and
 * nothing is hidden: the API refuses what the role does not allow anyway.
 */
export function useAccess(kbId: string) {
  const role = useKbs().data?.find((kb) => kb.id === kbId)?.my_role ?? undefined;
  return { role, canEdit: role !== "reader", canManage: role !== "reader" && role !== "editor" };
}

export function useOrganizations() {
  return useQuery({ queryKey: ["organizations"], queryFn: () => call(api.GET("/v1/organizations")) });
}

export function useBaseAccess(kbId: string) {
  return useQuery({
    queryKey: ["access", kbId],
    queryFn: () => call(api.GET("/v1/kbs/{kb_id}/access", { params: { path: { kb_id: kbId } } })),
  });
}

export function useBaseInvites(kbId: string) {
  return useQuery({
    queryKey: ["base-invites", kbId],
    queryFn: () => call(api.GET("/v1/kbs/{kb_id}/invites", { params: { path: { kb_id: kbId } } })),
  });
}

/** A change to who reaches the base; the bases list carries its general access, so it refreshes too. */
function useAccessChange<T>(kbId: string, request: (input: T) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: request,
    onSuccess: () => invalidate(queryClient, ["access", kbId], ["base-invites", kbId], ["kbs"]),
  });
}

export function useSetGeneralAccess(kbId: string) {
  return useAccessChange(kbId, (general_access: GeneralAccess) =>
    call(api.PUT("/v1/kbs/{kb_id}/access", { params: { path: { kb_id: kbId } }, body: { general_access } })),
  );
}

/** Members of the base's organization are added at once; anyone else gets an invite. */
export function useInviteToBase(kbId: string) {
  return useAccessChange(kbId, (body: { emails: string[]; role: BaseRole }) =>
    call(api.POST("/v1/kbs/{kb_id}/invites", { params: { path: { kb_id: kbId } }, body })),
  );
}

export function useSetBaseRole(kbId: string) {
  return useAccessChange(kbId, ({ accountId, role }: { accountId: string; role: BaseRole }) =>
    call(
      api.PUT("/v1/kbs/{kb_id}/members/{account_id}", {
        params: { path: { kb_id: kbId, account_id: accountId } },
        body: { role },
      }),
    ),
  );
}

export function useRemoveFromBase(kbId: string) {
  return useAccessChange(kbId, (accountId: string) =>
    call(
      api.DELETE("/v1/kbs/{kb_id}/members/{account_id}", { params: { path: { kb_id: kbId, account_id: accountId } } }),
    ),
  );
}

export function useResendInvite(kbId: string) {
  return useAccessChange(kbId, (inviteId: string) =>
    call(api.POST("/v1/invites/{invite_id}/resend", { params: { path: { invite_id: inviteId } } })),
  );
}

export function useRevokeInvite(kbId: string) {
  return useAccessChange(kbId, (inviteId: string) =>
    call(api.DELETE("/v1/invites/{invite_id}", { params: { path: { invite_id: inviteId } } })),
  );
}
