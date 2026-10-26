import createClient from "openapi-fetch";
import type { components, paths } from "./schema.gen";

type Schemas = components["schemas"];
export type ErrorResponse = Schemas["ErrorResponse"];
export type KbSummary = Schemas["KbSummary"];
export type Kb = Schemas["KbRead"];
export type TreeNode = Schemas["TreeNode"];
export type NodeDetail = Schemas["NodeDetail"];
export type NodeWithPath = Schemas["NodeWithPath"];
export type PageVersion = Schemas["PageVersionSummary"];
export type FileVersion = Schemas["FileVersionResponse"];
export type DiffLine = Schemas["DiffLine"];

/** The `details` of a `stale_page` error. */
export type StalePage = { current_version_id: string; markdown: string; diff: DiffLine[] };

// Same origin: the dev server proxies /v1 to the API, and the session cookie goes with every request.
export const api = createClient<paths>({ baseUrl: "" });
