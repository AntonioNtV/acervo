import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema.gen";
import { createPasskey, getPasskey } from "../webauthn";
import { useAccountChange, type Account } from "./account";
import { ApiError, call, invalidate } from "./request";

export type Passkey = components["schemas"]["PasskeyRead"];
export type PendingSignIn = components["schemas"]["PendingSignIn"];

/** What a password sign-in answered: the account, or the code step of two-step verification. */
export function isPending(answer: Account | PendingSignIn): answer is PendingSignIn {
  return "pending" in answer;
}

/** A sensitive change refused for lack of a recent sign-in: the reauthentication dialog's to handle. */
export function needsReauth(error: unknown): boolean {
  return error instanceof ApiError && error.code === "reauthentication_required";
}

/**
 * Signs in with a passkey the browser offers; on a session of the same account it confirms that session instead
 * (a recent sign-in). With `autofill`, the prompt waits in the email field's suggestions until aborted.
 */
export async function passkeySignIn(autofill?: AbortSignal): Promise<Account> {
  const { options } = await call(api.POST("/v1/passkeys/sign-in/options"));
  const credential = await getPasskey(options, autofill);
  return call(api.POST("/v1/passkeys/sign-in", { body: { credential } }));
}

export function usePasskeySignIn() {
  return useMutation({ mutationFn: () => passkeySignIn() });
}

/** What this server offers: no WhatsApp without a sender configured. */
export function useSecurityOptions() {
  return useQuery({ queryKey: ["security-options"], queryFn: () => call(api.GET("/v1/security/options")) });
}

export function usePasskeys() {
  return useQuery({ queryKey: ["passkeys"], queryFn: () => call(api.GET("/v1/passkeys")) });
}

/** After a passkey was added, renamed or removed: the list and `has_passkey`. */
function usePasskeyChange<T>(request: (input: T) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: request, onSuccess: () => invalidate(queryClient, ["passkeys"], ["me"]) });
}

/** Runs the browser's prompt for a new passkey and keeps it; needs a recent sign-in. */
export function useAddPasskey() {
  return usePasskeyChange(async () => {
    const { options } = await call(api.POST("/v1/passkeys/register/options"));
    const credential = await createPasskey(options);
    return call(api.POST("/v1/passkeys/register", { body: { credential } }));
  });
}

export function useRenamePasskey() {
  return usePasskeyChange(({ id, name }: { id: string; name: string }) =>
    call(api.PATCH("/v1/passkeys/{passkey_id}", { params: { path: { passkey_id: id } }, body: { name } })),
  );
}

/** Needs a recent sign-in; the last way into the account is refused with `last_way_in`. */
export function useRemovePasskey() {
  return usePasskeyChange((id: string) =>
    call(api.DELETE("/v1/passkeys/{passkey_id}", { params: { path: { passkey_id: id } } })),
  );
}

/** Email turns on at once; WhatsApp needs a recent sign-in, sends a code to `phone` and turns on once confirmed. */
export function useStartTwoFactor() {
  return useAccountChange((body: { method: "email" | "whatsapp"; phone?: string }) =>
    call(api.POST("/v1/two-factor", { body })),
  );
}

export function useConfirmTwoFactor() {
  return useAccountChange((code: string) => call(api.POST("/v1/two-factor/confirm", { body: { code } })));
}

export function useDisableTwoFactor() {
  return useAccountChange(() => call(api.DELETE("/v1/two-factor")));
}

/** Sets or changes the password and ends every other session; needs a recent sign-in. */
export function useSetPassword() {
  return useAccountChange((password: string) => call(api.PUT("/v1/account/password", { body: { password } })));
}

export function useUnlinkGoogle() {
  return useAccountChange(() => call(api.DELETE("/v1/auth/google/link")));
}

/** The password again: sensitive changes are allowed for the next 10 minutes. */
export function useReauthenticate() {
  return useMutation({
    mutationFn: (password: string) => call(api.POST("/v1/sessions/reauthenticate", { body: { password } })),
  });
}

/** The code of a pending sign-in starts the session. */
export function useFinishTwoFactor() {
  return useMutation({ mutationFn: (code: string) => call(api.POST("/v1/auth/two-factor", { body: { code } })) });
}

/** A new code for the pending sign-in; `email` sends it to the account email whatever the method. */
export function useResendTwoFactor() {
  return useMutation({
    mutationFn: (channel?: "email") => call(api.POST("/v1/auth/two-factor/resend", { body: { channel } })),
  });
}
