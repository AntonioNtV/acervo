const KEY = "acervo.lastPage";
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

/** After a base goes to the Lixeira, so `/` does not land inside it. */
export function forgetBase(kbId: string) {
  try {
    localStorage.removeItem(recentKey(kbId));
    if (localStorage.getItem(KEY)?.startsWith(`/kbs/${kbId}/`)) localStorage.removeItem(KEY);
  } catch {
    // Nothing was stored.
  }
}

/** After the last page turned out to be gone, so `/` falls back. */
export function forgetLastPage() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // Nothing was stored.
  }
}
