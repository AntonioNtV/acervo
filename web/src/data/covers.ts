import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, apiHeaders } from "../api/client";
import type { components, paths } from "../api/schema.gen";
import { ApiError, call, refreshTree } from "./request";

type NodeRead = components["schemas"]["NodeRead"];

/** The gallery, each slug a `--cover-<slug>` token; the first one is also what shows while an image loads. */
export const GALLERY = ["sage", "sand", "stone", "sky", "clay", "moss", "dawn", "dusk"] as const;

const GALLERY_PREFIX = "gallery:";
const UPLOAD = "/v1/nodes/{node_id}/cover" satisfies keyof paths;
// A link this close to its expiry is not handed to an <img>: it could expire before the image is read.
const EXPIRY_MARGIN_MS = 5_000;

export const galleryCover = (slug: string) => `${GALLERY_PREFIX}${slug}`;

export const isImageCover = (cover: string | null | undefined) => !!cover?.startsWith("image:");

/** The CSS background of a cover: its gallery token, or the placeholder under an uploaded image. */
export function coverBackground(cover: string): string {
  const slug = cover.startsWith(GALLERY_PREFIX) ? cover.slice(GALLERY_PREFIX.length) : GALLERY[0];
  return `var(--cover-${slug}, var(--cover-${GALLERY[0]}))`;
}

/** A PNG, JPEG or WebP becomes the node's cover; a wrong type or size rejects with `validation`. */
export function useUploadCover(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    // Multipart through XMLHttpRequest, as every upload of the app (`upload.ts`).
    mutationFn: (file: File) =>
      new Promise<NodeRead>((resolve, reject) => {
        const form = new FormData();
        form.append("file", file);
        const request = new XMLHttpRequest();
        request.open("POST", UPLOAD.replace("{node_id}", encodeURIComponent(nodeId)));
        for (const [name, value] of Object.entries(apiHeaders)) request.setRequestHeader(name, value);
        request.responseType = "json";
        request.onload = () => {
          if (request.status >= 200 && request.status < 300) return resolve(request.response as NodeRead);
          reject(new ApiError(request.status, request.response, request.statusText));
        };
        request.onerror = () => reject(new ApiError(0, null, "network error"));
        request.send(form);
      }),
    onSuccess: () => refreshTree(queryClient),
  });
}

/** A signed link to an uploaded cover for an `<img>`, which cannot send the key; asked again once it expired. */
export function useCoverLink(nodeId: string, cover: string | null) {
  return useQuery({
    queryKey: ["cover-link", nodeId, cover],
    enabled: isImageCover(cover),
    queryFn: async () => {
      const link = await call(api.POST("/v1/nodes/{node_id}/cover/link", { params: { path: { node_id: nodeId } } }));
      const signed = new URL(link.url);
      return { src: signed.pathname + signed.search, usableUntil: Date.parse(link.expires_at) - EXPIRY_MARGIN_MS };
    },
    staleTime: (query) => Math.max(0, (query.state.data?.usableUntil ?? 0) - Date.now()),
    refetchOnWindowFocus: false,
  });
}
