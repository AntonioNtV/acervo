import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components, paths } from "../api/schema.gen";
import { call, samePath } from "./request";
import { send, type OnProgress } from "./upload";

type Attachment = components["schemas"]["Attachment"];

const UPLOAD = "/v1/pages/{node_id}/attachments" satisfies keyof paths;
// A link this close to its expiry is not handed to an <img> or a player: it could expire before the bytes are read.
const EXPIRY_MARGIN_MS = 5_000;

/** Any file into the page, outside the tree; over the limit rejects with `attachment_too_large`. */
export function uploadAttachment(pageId: string, file: File, onProgress?: OnProgress) {
  return send<Attachment>(UPLOAD.replace("{node_id}", encodeURIComponent(pageId)), { file }, onProgress);
}

export function useUploadAttachment(pageId: string) {
  return useMutation({
    mutationFn: ({ file, onProgress }: { file: File; onProgress?: OnProgress }) =>
      uploadAttachment(pageId, file, onProgress),
  });
}

/** A signed link to an attachment for an `<img>`, `<video>` or `<audio>`, which cannot send the key; asked again once it expired. */
export function useAttachmentLink(pageId: string, name: string | null) {
  return useQuery({
    queryKey: ["attachment-link", pageId, name],
    enabled: name !== null,
    queryFn: async () => {
      const link = await call(
        api.POST("/v1/pages/{node_id}/attachments/{name}/link", { params: { path: { node_id: pageId, name: name! } } }),
      );
      return { src: samePath(link.url), usableUntil: Date.parse(link.expires_at) - EXPIRY_MARGIN_MS };
    },
    staleTime: (query) => Math.max(0, (query.state.data?.usableUntil ?? 0) - Date.now()),
    refetchOnWindowFocus: false,
  });
}
