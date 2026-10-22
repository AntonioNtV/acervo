const KEY = "acervo.lastPage";

/** The path of the last node opened in this browser, as `/kbs/{kb}/n/{node}`; null when none or no storage. */
export function readLastPage(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function rememberPage(kbId: string, nodeId: string) {
  try {
    localStorage.setItem(KEY, `/kbs/${kbId}/n/${nodeId}`);
  } catch {
    // Without storage, opening Acervo lands on the first page instead.
  }
}

/** After a base goes to the Lixeira, so `/` does not land inside it. */
export function forgetBase(kbId: string) {
  try {
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
