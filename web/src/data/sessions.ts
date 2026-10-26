import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema.gen";
import { call, invalidate } from "./request";

export type Session = components["schemas"]["SessionRead"];
export type SecurityEvent = components["schemas"]["SecurityEventRead"];
export type AuditEvent = components["schemas"]["AuditEventRead"];

/** Every open session of the account, the last used first; `current` is this browser's. */
export function useSessions() {
  return useQuery({ queryKey: ["sessions"], queryFn: () => call(api.GET("/v1/sessions")) });
}

/** Ending one shows in the activity too. */
function useSessionChange<T>(request: (input: T) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: request, onSettled: () => invalidate(queryClient, ["sessions"], ["activity"]) });
}

/** Another session of the account; this one ends by signing out. */
export function useEndSession() {
  return useSessionChange((sessionId: string) =>
    call(api.DELETE("/v1/sessions/{session_id}", { params: { path: { session_id: sessionId } } })),
  );
}

export function useEndOtherSessions() {
  return useSessionChange(() => call(api.POST("/v1/sessions/end-others")));
}

/** The account's last 90 days, newest first. */
export function useActivity() {
  return useQuery({ queryKey: ["activity"], queryFn: () => call(api.GET("/v1/security/activity")) });
}

/** The organization's last 90 days, newest first; only its Owners and Admins may read it. */
export function useAudit(organizationId: string) {
  return useQuery({
    queryKey: ["audit", organizationId],
    queryFn: () =>
      call(api.GET("/v1/organizations/{organization_id}/audit", { params: { path: { organization_id: organizationId } } })),
  });
}

/** The same audit as a CSV download, which the API sends as an attachment. */
export const auditCsv = (organizationId: string) => `/v1/organizations/${organizationId}/audit.csv`;
