import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import type { KbSummary } from "../../api/queries";
import { renderWithApi, respond } from "../../testing";

/** The bases routes over an in-memory list, through the shared fake API. */
export function fakeBases(initial: KbSummary[]) {
  const kbs = initial.map((kb) => ({ ...kb }));
  respond("GET", "/kbs", () => ({ body: kbs.filter((kb) => !kb.deleted_at) }));
  respond("GET", "/trash/kbs", () => ({ body: kbs.filter((kb) => kb.deleted_at) }));
  respond("POST", "/kbs", (_url, body) => {
    const created = summary({ id: `kb-${kbs.length + 1}`, ...(body as { name: string; description: string }) });
    kbs.push(created);
    return { status: 201, body: created };
  });
  for (const kb of kbs) {
    respond("DELETE", `/kbs/${kb.id}`, () => {
      kb.deleted_at = new Date().toISOString();
      return { body: kb };
    });
    respond("POST", `/kbs/${kb.id}/restore`, () => {
      kb.deleted_at = null;
      return { body: kb };
    });
  }
  return kbs;
}

export function summary(fields: Partial<KbSummary> & Pick<KbSummary, "id" | "name">): KbSummary {
  return { description: "", deleted_at: null, pages: 0, files: 0, last_edit: new Date().toISOString(), ...fields };
}

export function renderPage(page: ReactNode) {
  return renderWithApi(<MemoryRouter>{page}</MemoryRouter>);
}
