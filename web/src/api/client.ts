import createClient from "openapi-fetch";
import type { paths } from "./schema.gen";

export const apiBaseUrl: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const api = createClient<paths>({ baseUrl: apiBaseUrl });
