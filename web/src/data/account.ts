import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { call } from "./request";

/** The signed-in account; a 401 when there is no session. */
export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => call(api.GET("/v1/auth/me")) });
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
