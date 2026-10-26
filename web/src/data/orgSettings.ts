import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema.gen";
import { call, invalidate } from "./request";

export type Organization = components["schemas"]["OrganizationRead"];
export type Member = components["schemas"]["MemberRead"];
export type Invite = components["schemas"]["InviteRead"];
export type InvitePreview = components["schemas"]["InvitePreview"];
export type OrgRole = Organization["my_role"];
export type BaseAccess = Organization["new_base_access"];

// shortcut: the same key and fallback as card 07's helper in data/organizations.ts; use that one once both are merged.
const CURRENT_KEY = "acervo.organization";

/** The organization this browser shows; null for none yet, which means the Pessoal. */
export function readCurrentOrganization(): string | null {
  try {
    return localStorage.getItem(CURRENT_KEY);
  } catch {
    return null;
  }
}

export function rememberCurrentOrganization(id: string) {
  try {
    localStorage.setItem(CURRENT_KEY, id);
  } catch {
    // Without storage, Acervo opens on the Pessoal.
  }
}

/** The person's organizations, Pessoal first. */
export function useOrganizations() {
  return useQuery({ queryKey: ["organizations"], queryFn: () => call(api.GET("/v1/organizations")) });
}

const path = (organizationId: string) => ({ params: { path: { organization_id: organizationId } } });

/** A change whose answer is the organization as it is now. */
function useOrganizationChange<T>(request: (input: T) => Promise<Organization>) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: request, onSuccess: () => invalidate(queryClient, ["organizations"]) });
}

export function useUpdateOrganization(organizationId: string) {
  return useOrganizationChange((body: { name?: string; new_base_access?: BaseAccess }) =>
    call(api.PATCH("/v1/organizations/{organization_id}", { ...path(organizationId), body })),
  );
}

/** A PNG, JPEG or WebP whose centered square becomes the logo; a wrong type or size rejects with `validation`. */
export function useSetLogo(organizationId: string) {
  return useOrganizationChange((file: File) =>
    call(
      api.PUT("/v1/organizations/{organization_id}/logo", {
        ...path(organizationId),
        body: { file: file as unknown as string },
        bodySerializer: (body) => {
          const form = new FormData();
          form.append("file", body.file);
          return form;
        },
      }),
    ),
  );
}

export function useRemoveLogo(organizationId: string) {
  return useOrganizationChange(() => call(api.DELETE("/v1/organizations/{organization_id}/logo", path(organizationId))));
}

export function useMembers(organizationId: string) {
  return useQuery({
    queryKey: ["members", organizationId],
    queryFn: () => call(api.GET("/v1/organizations/{organization_id}/members", path(organizationId))),
  });
}

/** Refused with `last_owner` when it would leave the organization without an Owner. */
export function useChangeRole(organizationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ accountId, role }: { accountId: string; role: OrgRole }) =>
      call(
        api.PATCH("/v1/organizations/{organization_id}/members/{account_id}", {
          params: { path: { organization_id: organizationId, account_id: accountId } },
          body: { role },
        }),
      ),
    // The person may have changed their own role.
    onSettled: () => invalidate(queryClient, ["members", organizationId], ["organizations"]),
  });
}

export function useRemoveMember(organizationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (accountId: string) =>
      call(
        api.DELETE("/v1/organizations/{organization_id}/members/{account_id}", {
          params: { path: { organization_id: organizationId, account_id: accountId } },
        }),
      ),
    onSettled: () => invalidate(queryClient, ["members", organizationId]),
  });
}

/** Every base of the organization; its Owners and Admins see them all. */
export function useOrganizationBases(organizationId: string) {
  return useQuery({
    queryKey: ["kbs", "organization", organizationId],
    queryFn: () => call(api.GET("/v1/kbs", { params: { query: { organization_id: organizationId } } })),
  });
}

/** Invites not yet accepted nor revoked, expired ones included. */
export function useOrgInvites(organizationId: string) {
  return useQuery({
    queryKey: ["invites", organizationId],
    queryFn: () => call(api.GET("/v1/organizations/{organization_id}/invites", path(organizationId))),
  });
}

/** One role for every email; refused with `already_member`, naming them in `details.emails`. */
export function useInvite(organizationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { emails: string[]; role: OrgRole }) =>
      call(api.POST("/v1/organizations/{organization_id}/invites", { ...path(organizationId), body })),
    onSuccess: () => invalidate(queryClient, ["invites", organizationId]),
  });
}

/** A new 7-day link; refused with 429 within a minute of the last one. */
export function useResendInvite(organizationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (inviteId: string) =>
      call(api.POST("/v1/invites/{invite_id}/resend", { params: { path: { invite_id: inviteId } } })),
    onSuccess: () => invalidate(queryClient, ["invites", organizationId]),
  });
}

export function useRevokeInvite(organizationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (inviteId: string) =>
      call(api.DELETE("/v1/invites/{invite_id}", { params: { path: { invite_id: inviteId } } })),
    onSuccess: () => invalidate(queryClient, ["invites", organizationId]),
  });
}

/** What a link `/convite/{token}` invites to, readable without a session; `code_invalid` for a revoked or used one. */
export function useInvitePreview(token: string) {
  return useQuery({
    queryKey: ["invite", token],
    queryFn: () => call(api.GET("/v1/invites/by-token/{token}", { params: { path: { token } } })),
    retry: false,
  });
}

/** Refused with `invite_email_mismatch` when the session's email is not the invite's. */
export function useAcceptInvite() {
  return useMutation({
    mutationFn: (token: string) => call(api.POST("/v1/invites/accept", { body: { token } })),
  });
}
