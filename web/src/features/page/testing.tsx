import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { Mock } from "vitest";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import type { NodeDetail, Version } from "../../api/queries";
import { I18nProvider } from "../../i18n";
import { PageView } from "./PageView";

// jsdom has no layout, and CodeMirror measures text ranges.
Range.prototype.getClientRects ??= () => [] as unknown as DOMRectList;
Range.prototype.getBoundingClientRect ??= () => new DOMRect();

type Handler = unknown | ((body: unknown) => Response | unknown);

export function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/**
 * Answers the API client's requests from a table keyed `"<METHOD> <path>"`. A function gets the JSON body and
 * returns a `Response` or the 200 body. Each test file stubs `fetch` with `vi.hoisted`, before the client is built.
 */
export function serve(fetchMock: Mock<(request: Request) => Promise<Response>>, routes: Record<string, Handler>) {
  fetchMock.mockImplementation(async (request: Request) => {
    const key = `${request.method} ${new URL(request.url).pathname}`;
    if (!(key in routes)) return json(404, { error: "NotFoundError", message: key });
    const handler = routes[key];
    if (typeof handler !== "function") return json(200, handler);
    const text = await request.text();
    const result = (handler as (body: unknown) => unknown)(text ? JSON.parse(text) : undefined);
    return result instanceof Response ? result : json(200, result);
  });
}

export function pageNode(page: Partial<NonNullable<NodeDetail["page"]>> = {}): NodeDetail {
  return {
    id: "page-1",
    kb_id: "kb-1",
    parent_id: "folder-1",
    kind: "page",
    title: "Emissão de apólice",
    deleted_at: null,
    path: "Bradesco/Residencial/Emissão de apólice",
    page: { version_id: "v2", markdown: "## Documentos\n", draft: null, links: {}, sections: [], ...page },
    file: null,
    versions: 2,
  };
}

export const versions: Version[] = [
  { id: "v2", created_at: "2026-10-14T16:10:00Z", author: "user", size: null },
  { id: "v1", created_at: "2026-10-14T11:03:00Z", author: "user", size: null },
];

export function renderPage() {
  const router = createMemoryRouter([{ path: "/kbs/:kbId/n/:nodeId", element: <PageView /> }], {
    initialEntries: ["/kbs/kb-1/n/page-1"],
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <RouterProvider router={router} />
      </I18nProvider>
    </QueryClientProvider>,
  );
}
