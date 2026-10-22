import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import type { Middleware } from "openapi-fetch";
import { api } from "../../api/client";
import type { KbSummary } from "../../api/queries";
import { Providers } from "../../app/Providers";

/** The bases routes over an in-memory list, answered inside the client so no request leaves the test. */
export function fakeBasesApi(initial: KbSummary[]) {
  const kbs = initial.map((kb) => ({ ...kb }));
  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

  const middleware: Middleware = {
    async onRequest({ request }) {
      const { pathname } = new URL(request.url);
      const [, first, id, action] = pathname.split("/");
      const kb = kbs.find((each) => each.id === id);
      if (request.method === "GET" && pathname === "/kbs") return json(kbs.filter((each) => !each.deleted_at));
      if (request.method === "GET" && pathname === "/trash/kbs") return json(kbs.filter((each) => each.deleted_at));
      if (request.method === "POST" && pathname === "/kbs") {
        const body = await request.json();
        const created = summary({ id: `kb-${kbs.length + 1}`, ...body });
        kbs.push(created);
        return json(created, 201);
      }
      if (first === "kbs" && kb && request.method === "DELETE") {
        kb.deleted_at = new Date().toISOString();
        return json(kb);
      }
      if (first === "kbs" && kb && request.method === "POST" && action === "restore") {
        kb.deleted_at = null;
        return json(kb);
      }
      return json({ error: "NotFoundError", message: "not faked" }, 404);
    },
  };
  api.use(middleware);
  return { kbs, stop: () => api.eject(middleware) };
}

export function summary(fields: Partial<KbSummary> & Pick<KbSummary, "id" | "name">): KbSummary {
  return { description: "", deleted_at: null, pages: 0, files: 0, last_edit: new Date().toISOString(), ...fields };
}

export function renderPage(page: ReactNode) {
  return render(
    <Providers>
      <MemoryRouter>{page}</MemoryRouter>
    </Providers>,
  );
}
