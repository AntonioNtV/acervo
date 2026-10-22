import type { QueryClient } from "@tanstack/react-query";
import type { ErrorResponse } from "../api/client";

/** Any answer outside 2xx; `status` 0 when the request never reached the API. Its message is never shown. */
export class ApiError extends Error {
  readonly body: ErrorResponse;

  /** `raw` is whatever the response held: the API's JSON error, or the text of a proxy's 500. */
  constructor(
    readonly status: number,
    raw: unknown,
    statusText = "",
  ) {
    const body =
      typeof raw === "object" && raw !== null && "error" in raw && "message" in raw
        ? (raw as ErrorResponse)
        : { error: "", message: statusText || `HTTP ${status}` };
    super(body.message);
    this.body = body;
  }

  /** The API's error code (`not_found`, `duplicate`, …); empty when the answer was not the API's. */
  get code(): string {
    return this.body.error;
  }

  get details(): Record<string, unknown> {
    return this.body.details ?? {};
  }
}

export async function call<T>(request: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await request;
  if (!response.ok) throw new ApiError(response.status, error, response.statusText);
  return data as T;
}

export function invalidate(queryClient: QueryClient, ...prefixes: string[][]) {
  return Promise.all(prefixes.map((queryKey) => queryClient.invalidateQueries({ queryKey })));
}

/** After anything that changes where nodes are or what they are called; a page rename rewrites other pages too. */
export function refreshTree(queryClient: QueryClient) {
  return invalidate(queryClient, ["children"], ["search"], ["trash"], ["node"], ["kbs"]);
}

/** After a node's content changed: a page version, a replaced or restored file. */
export function refreshContent(queryClient: QueryClient, nodeId: string) {
  return invalidate(queryClient, ["node", nodeId], ["versions", nodeId], ["diff", nodeId], ["kbs"]);
}
