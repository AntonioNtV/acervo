import * as RadixDialog from "@radix-ui/react-dialog";
import { apiHeaders } from "../api/client";
import type { paths } from "../api/schema.gen";
import { useI18n } from "../i18n";
import { Icon } from "../ui/Icon";
import { IconButton } from "../ui/IconButton";
import { PdfViewer } from "./PdfViewer";

const RAW = "/v1/pages/{node_id}/attachments/{name}/raw" satisfies keyof paths;

/**
 * A PDF attached to a page, in Acervo's reader over the page: read only, without versions or actions. It reads with
 * the key, as the tree's reader does, since a signed link would expire while pdf.js still asks for ranges.
 */
export function AttachmentPdfDialog({ pageId, name, onClose }: { pageId: string; name: string; onClose: () => void }) {
  const { t } = useI18n();
  const url = RAW.replace("{node_id}", encodeURIComponent(pageId)).replace("{name}", encodeURIComponent(name));
  return (
    <RadixDialog.Root open onOpenChange={(next) => !next && onClose()}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 bg-[color-mix(in_srgb,var(--text)_24%,transparent)]" />
        <RadixDialog.Content
          aria-describedby={undefined}
          className="fixed inset-6 flex flex-col overflow-hidden rounded-[12px] border border-line-2 bg-desk"
        >
          <RadixDialog.Title className="sr-only">{name}</RadixDialog.Title>
          <PdfViewer source={{ url, httpHeaders: apiHeaders }} title={name}>
            <RadixDialog.Close asChild>
              <IconButton aria-label={t("file.versions.close")}>
                <Icon name="close" />
              </IconButton>
            </RadixDialog.Close>
          </PdfViewer>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
