import { useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { ORG_KEY } from "../data/organizations";
import { browserLang, useI18n } from "../i18n";
import { useTheme } from "./theme";

const KEY = "acervo.lastPage";
const ACCOUNT_KEY = "acervo.account";
const RECENT_MAX = 10;

const recentKey = (kbId: string) => `acervo.recent.${kbId}`;

/** The path of the last node opened in this browser, as `/kbs/{kb}/n/{node}`; null when none or no storage. */
export function readLastPage(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

/** The nodes last opened in this base in this browser, the latest first, each once. */
export function readRecentPages(kbId: string): string[] {
  try {
    const ids: unknown = JSON.parse(localStorage.getItem(recentKey(kbId)) ?? "[]");
    return Array.isArray(ids) ? ids.filter((id): id is string => typeof id === "string") : [];
  } catch {
    return [];
  }
}

export function rememberPage(kbId: string, nodeId: string) {
  try {
    localStorage.setItem(KEY, `/kbs/${kbId}/n/${nodeId}`);
    const recent = [nodeId, ...readRecentPages(kbId).filter((id) => id !== nodeId)].slice(0, RECENT_MAX);
    localStorage.setItem(recentKey(kbId), JSON.stringify(recent));
  } catch {
    // Without storage, opening Acervo lands on the first page instead.
  }
}

/** After a recent node turned out to live in another base now. */
export function forgetRecent(kbId: string, nodeId: string) {
  try {
    localStorage.setItem(recentKey(kbId), JSON.stringify(readRecentPages(kbId).filter((id) => id !== nodeId)));
  } catch {
    // Nothing was stored.
  }
}

/** After a base goes to the Lixeira, so `/` does not land inside it. */
export function forgetBase(kbId: string) {
  try {
    localStorage.removeItem(recentKey(kbId));
    if (localStorage.getItem(KEY)?.startsWith(`/kbs/${kbId}/`)) localStorage.removeItem(KEY);
  } catch {
    // Nothing was stored.
  }
}

/** The account this browser last showed, to notice a switch that came through a full page load (Google). */
export function readAccountId(): string | null {
  try {
    return localStorage.getItem(ACCOUNT_KEY);
  } catch {
    return null;
  }
}

export function rememberAccountId(id: string) {
  try {
    localStorage.setItem(ACCOUNT_KEY, id);
  } catch {
    // Without storage, a switch through Google keeps the last account's pages and theme.
  }
}

/**
 * Drops what the last account left in this browser, so whoever signs in next does not land where it was or see its
 * cache: its queries, pages, organization and id, and its theme and language, as the screens follow the browser again.
 */
export function useForgetAccount() {
  const queryClient = useQueryClient();
  const { setTheme } = useTheme();
  const { setLang } = useI18n();
  return useCallback(() => {
    queryClient.clear();
    try {
      for (const key of Object.keys(localStorage))
        if (key === KEY || key === ACCOUNT_KEY || key === ORG_KEY || key.startsWith(recentKey(""))) localStorage.removeItem(key);
    } catch {
      // Nothing was stored.
    }
    setTheme("system");
    setLang(browserLang());
  }, [queryClient, setTheme, setLang]);
}

/** After the last page turned out to be gone, so `/` falls back. */
export function forgetLastPage() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // Nothing was stored.
  }
}
