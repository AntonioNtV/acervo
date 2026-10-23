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
export type DiffLine = Schemas["DiffLine"];

/** Sent with every request, the raw file's included; the key never goes in a URL. */
export const apiHeaders: Record<string, string> = { "X-API-Key": import.meta.env.VITE_API_KEY ?? "" };

// Same origin: the dev server proxies /v1 to the API.
export const api = createClient<paths>({ baseUrl: "", headers: apiHeaders });
