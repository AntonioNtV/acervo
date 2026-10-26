import { respond } from "../../api/testing";
import type { Account } from "../../data/account";

/** The signed-in account `GET /v1/auth/me` answers with, changed by `overrides`. */
export function signedIn(overrides: Partial<Account> = {}): Account {
  const account: Account = {
    id: "acc-1",
    name: "Antonio Bertino",
    email: "antonio@segura.com.br",
    email_verified: true,
    has_google: false,
    has_password: true,
    photo_url: null,
    preferences: { theme: "light", page_width: "default", language: "pt-BR", start_page: "last" },
    ...overrides,
  };
  respond("GET", "/v1/auth/me", { body: account });
  return account;
}
