import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import type { KbSummary } from "../../api/client";
import { renderWithApi, respond } from "../../api/testing";

/** The bases routes over an in-memory list, through the shared fake API. */
export function fakeBases(initial: KbSummary[]) {
  const kbs = initial.map((kb) => ({ ...kb }));
  respond("GET", "/v1/kbs", () => ({ body: kbs.filter((kb) => !kb.deleted_at) }));
  respond("GET", "/v1/kbs/trash", () => ({ body: kbs.filter((kb) => kb.deleted_at) }));
  respond("POST", "/v1/kbs", (_url, body) => {
    const created = summary({ id: `kb-${kbs.length + 1}`, ...(body as { name: string; description: string }) });
    kbs.push(created);
    return { status: 201, body: created };
  });
  for (const kb of kbs) {
    respond("DELETE", `/v1/kbs/${kb.id}`, () => {
      kb.deleted_at = new Date().toISOString();
      return { body: kb };
    });
    respond("POST", `/v1/kbs/${kb.id}/restore`, () => {
      kb.deleted_at = null;
      return { body: kb };
    });
  }
  return kbs;
}

export function summary(fields: Partial<KbSummary> & Pick<KbSummary, "id" | "name">): KbSummary {
  const at = new Date().toISOString();
  return { description: "", deleted_at: null, created_at: at, updated_at: at, pages: 0, files: 0, last_edit: at, ...fields };
}

export function renderPage(page: ReactNode) {
  return renderWithApi(<MemoryRouter>{page}</MemoryRouter>);
}
