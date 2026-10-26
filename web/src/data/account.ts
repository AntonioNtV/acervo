import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema.gen";
import { call, invalidate } from "./request";

export type Account = components["schemas"]["AccountRead"];
export type Preferences = components["schemas"]["Preferences"];

/** The signed-in account; a 401 when there is no session. */
export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => call(api.GET("/v1/auth/me")) });
}

/** A change whose answer is the account as it is now. */
function useAccountChange<T>(request: (input: T) => Promise<Account>) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: request, onSuccess: (account) => queryClient.setQueryData(["me"], account) });
}

export function useRename() {
  return useAccountChange((name: string) => call(api.PATCH("/v1/account", { body: { name } })));
}

/** A PNG, JPEG or WebP whose centered square becomes the photo; a wrong type or size rejects with `validation`. */
export function useSetPhoto() {
  return useAccountChange((file: File) =>
    call(
      api.PUT("/v1/account/photo", {
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

export function useRemovePhoto() {
  return useAccountChange(() => call(api.DELETE("/v1/account/photo")));
}

/**
 * Sends a code to the new address, once the current password is right when the account has one; the email changes
 * only once that code is confirmed.
 */
export function useRequestEmailChange() {
  return useMutation({
    mutationFn: (body: { new_email: string; password?: string }) => call(api.POST("/v1/account/email", { body })),
  });
}

export function useConfirmEmailChange() {
  return useAccountChange((code: string) => call(api.POST("/v1/account/email/confirm", { body: { code } })));
}

/**
 * Changes some preferences on the account, which takes them all at once. The cache holds the change before the
 * request leaves, so a second change made before the first is answered builds on it; with no account loaded, nothing
 * is sent.
 */
export function useSetPreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    // One at a time, so quick changes reach the server in the order they were made.
    scope: { id: "preferences" },
    mutationFn: async (change: Partial<Preferences>) => {
      const me = queryClient.getQueryData<Account>(["me"]);
      if (!me) return;
      const preferences = { ...me.preferences, ...change };
      queryClient.setQueryData<Account>(["me"], { ...me, preferences });
      await call(api.PUT("/v1/account/preferences", { body: preferences }));
    },
    onError: () => invalidate(queryClient, ["me"]),
  });
}

/** Ends the session on the server, not only in this browser. */
export function useSignOut() {
  return useMutation({ mutationFn: () => call(api.POST("/v1/auth/sign-out")) });
}

export function useSignIn() {
  return useMutation({
    mutationFn: (body: { email: string; password: string }) => call(api.POST("/v1/auth/sign-in", { body })),
  });
}

/** Creates the account and sends the code; the session starts only once the code is confirmed. */
export function useSignUp() {
  return useMutation({
    mutationFn: (body: { name: string; email: string; password: string }) =>
      call(api.POST("/v1/auth/sign-up", { body })),
  });
}

export function useVerifyEmail() {
  return useMutation({
    mutationFn: (body: { email: string; code: string }) => call(api.POST("/v1/auth/verify-email", { body })),
  });
}

export function useResendCode() {
  return useMutation({
    mutationFn: (email: string) => call(api.POST("/v1/auth/resend-code", { body: { email } })),
  });
}

/** Always answers the same, whether or not the email has an account. */
export function useRequestReset() {
  return useMutation({
    mutationFn: (email: string) => call(api.POST("/v1/auth/reset", { body: { email } })),
  });
}

export function useConfirmReset() {
  return useMutation({
    mutationFn: (body: { token: string; password: string }) => call(api.POST("/v1/auth/reset/confirm", { body })),
  });
}

/** Links Google to the account that already had the email, after that account's password. */
export function useLinkGoogle() {
  return useMutation({
    mutationFn: (body: { token: string; password: string }) => call(api.POST("/v1/auth/google/link", { body })),
  });
}
