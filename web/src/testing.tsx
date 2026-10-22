import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import createClient from "openapi-fetch";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { paths } from "./api/schema.gen";
import { I18nProvider } from "./i18n";

/** `body` is sent as JSON, or as plain text when it is a string (a proxy's 500). */
type Reply = { status?: number; body: unknown };
type Handler = { method: string; path: string; reply: (url: URL, body: unknown) => Reply };
type Call = { method: string; path: string; query: string; body: unknown };

let handlers: Handler[] = [];
export const calls: Call[] = [];

/** Answers `method path` (path without query) from now on; the last one registered wins. */
export function respond(method: string, path: string, reply: Reply | ((url: URL, body: unknown) => Reply)) {
  handlers.unshift({ method, path, reply: typeof reply === "function" ? reply : () => reply });
}

export function resetApi() {
  handlers = [];
  calls.length = 0;
}

async function fakeFetch(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const text = await request.text();
  const body = text ? JSON.parse(text) : undefined;
  calls.push({ method: request.method, path: url.pathname, query: url.search, body });
  const handler = handlers.find((h) => h.method === request.method && h.path === url.pathname);
  const reply = handler?.reply(url, body) ?? { status: 404, body: { error: "NotFoundError", message: "not found" } };
  const plain = typeof reply.body === "string";
  return new Response(plain ? (reply.body as string) : JSON.stringify(reply.body), {
    status: reply.status ?? 200,
    headers: { "Content-Type": plain ? "text/plain" : "application/json" },
  });
}

/**
 * For `vi.mock("<…>/api/client", () => import("<…>/testing").then((m) => m.mockClient()))`: the generated client,
 * talking to the handlers above. openapi-fetch keeps the `fetch` it finds when built, so the client is replaced.
 */
export function mockClient() {
  const apiBaseUrl = "http://api.test";
  return { apiBaseUrl, api: createClient<paths>({ baseUrl: apiBaseUrl, fetch: fakeFetch }) };
}

/** Also gives the query client, to make a test refetch. */
export function renderWithApi(ui: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const rendered = render(
    <QueryClientProvider client={queryClient}>
      <I18nProvider>{ui}</I18nProvider>
    </QueryClientProvider>,
  );
  return { ...rendered, queryClient };
}

/** Renders `ui` as the base frame does, at `/kbs/:kbId/n/:nodeId`. */
export function renderInBase(ui: ReactNode, path = "/kbs/kb-1") {
  return renderWithApi(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/kbs/:kbId" element={ui}>
          <Route path="n/:nodeId" element={null} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

export function node(id: string, kind: "folder" | "page" | "file", title: string, parent_id: string | null = null) {
  return { id, kb_id: "kb-1", parent_id, kind, title, deleted_at: null, protected: false };
}
