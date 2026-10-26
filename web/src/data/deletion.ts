import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { switchOrganization, useOrganizations, type Organization } from "./organizations";
import { call, invalidate } from "./request";

/** 403 `reauthentication_required` without a recent sign-in; the session ends with the account. */
export function useDeleteAccount() {
  return useMutation({ mutationFn: () => call(api.DELETE("/v1/account")) });
}

/** Owners only, with a recent sign-in; the person is back on their Pessoal. */
export function useDeleteOrganization(organizationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      call(api.DELETE("/v1/organizations/{organization_id}", { params: { path: { organization_id: organizationId } } })),
    onSuccess: () => {
      switchOrganization(null);
      return invalidate(queryClient, ["organizations"], ["kbs"], ["trash-kbs"], ["favorites"]);
    },
  });
}

/**
 * The person's organizations other than the Pessoal: those that go with the account, where it is the only Owner, and
 * those it only leaves; undefined until the members of the ones it owns are read.
 */
export function useAccountOrganizations(): { sole: Organization[]; left: Organization[] } | undefined {
  const organizations = useOrganizations().data?.filter((org) => !org.personal);
  const owned = organizations?.filter((org) => org.my_role === "owner") ?? [];
  const members = useQueries({
    queries: owned.map((org) => ({
      queryKey: ["members", org.id],
      queryFn: () =>
        call(api.GET("/v1/organizations/{organization_id}/members", { params: { path: { organization_id: org.id } } })),
    })),
  });
  if (!organizations || members.some((query) => query.isPending)) return undefined;
  const sole = owned.filter((_org, i) => members[i]?.data?.filter((member) => member.role === "owner").length === 1);
  return { sole, left: organizations.filter((org) => !sole.includes(org)) };
}
