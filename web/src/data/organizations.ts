import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import { api } from "../api/client";
import type { components } from "../api/schema.gen";
import { call, invalidate } from "./request";

export type Organization = components["schemas"]["OrganizationRead"];

export const ORG_KEY = "acervo.org";

// Holds the choice when the browser keeps no storage; with storage, storage is what is read.
let memory: string | null = null;
const listeners = new Set<() => void>();

function readOrgId(): string | null {
  try {
    return localStorage.getItem(ORG_KEY);
  } catch {
    return memory;
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Makes `org` the current organization in this browser; the Pessoal is kept as no choice, the fallback. */
export function switchOrganization(org: Organization) {
  memory = org.personal ? null : org.id;
  try {
    if (memory) localStorage.setItem(ORG_KEY, memory);
    else localStorage.removeItem(ORG_KEY);
  } catch {
    // The choice holds until the page reloads.
  }
  for (const listener of listeners) listener();
}

/** The person's organizations: Pessoal first, then by name. */
export function useOrganizations() {
  return useQuery({ queryKey: ["organizations"], queryFn: () => call(api.GET("/v1/organizations")) });
}

/**
 * The current organization, and `id` to ask the API for its bases: undefined for the Pessoal, which is what the API
 * answers without one. Until the organizations load, the one chosen in this browser.
 */
export function useCurrentOrganization() {
  const chosen = useSyncExternalStore(subscribe, readOrgId);
  const organizations = useOrganizations().data;
  const current = organizations?.find((org) => org.id === chosen) ?? organizations?.find((org) => org.personal);
  const id = organizations ? (current?.personal ? undefined : current?.id) : (chosen ?? undefined);
  return { organizations, current, id };
}

/** Creates an organization the person owns; it is listed at once, before the list is read again. */
export function useCreateOrganization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => call(api.POST("/v1/organizations", { body: { name } })),
    onSuccess: (org) => {
      queryClient.setQueryData<Organization[]>(["organizations"], (orgs) => orgs && [...orgs, org]);
      return invalidate(queryClient, ["organizations"]);
    },
  });
}

/** A PNG, JPEG or WebP whose centered square becomes the logo; a wrong type or size rejects with `validation`. */
export function useSetOrganizationLogo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orgId, file }: { orgId: string; file: File }) =>
      call(
        api.PUT("/v1/organizations/{organization_id}/logo", {
          params: { path: { organization_id: orgId } },
          body: { file: file as unknown as string },
          bodySerializer: (body) => {
            const form = new FormData();
            form.append("file", body.file);
            return form;
          },
        }),
      ),
    onSuccess: () => invalidate(queryClient, ["organizations"]),
  });
}

/**
 * The organization of the person's that lists base `kbId`, the Pessoal for a base shared with them as a guest; null
 * when none does. Only asked for a base the current organization does not list.
 */
export function useBaseOrganization(kbId: string | undefined, enabled: boolean) {
  const organizations = useOrganizations().data;
  return useQuery({
    queryKey: ["base-organization", kbId],
    enabled: Boolean(kbId && organizations && enabled),
    // shortcut: one list per organization until one has the base, fine for a handful; a route answering a base's
    // organization would replace it.
    queryFn: async () => {
      for (const org of organizations ?? []) {
        const query = org.personal ? {} : { organization_id: org.id };
        const kbs = await call(api.GET("/v1/kbs", { params: { query } }));
        if (kbs.some((kb) => kb.id === kbId)) return org;
      }
      return null;
    },
  });
}
