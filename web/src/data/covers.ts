import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components, paths } from "../api/schema.gen";
import { call, refreshTree, samePath } from "./request";
import { send } from "./upload";

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
    mutationFn: (file: File) => send<NodeRead>(UPLOAD.replace("{node_id}", encodeURIComponent(nodeId)), { file }),
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
      return { src: samePath(link.url), usableUntil: Date.parse(link.expires_at) - EXPIRY_MARGIN_MS };
    },
    staleTime: (query) => Math.max(0, (query.state.data?.usableUntil ?? 0) - Date.now()),
    refetchOnWindowFocus: false,
  });
}
