import { rawFileUrl } from "../../api/queries";
import { useI18n } from "../../i18n";

/** "Baixar": the raw route answers with `Content-Disposition: attachment`, so a plain link downloads. */
export function DownloadLink({ nodeId, versionId }: { nodeId: string; versionId?: string }) {
  const { t } = useI18n();
  return (
    <a
      href={rawFileUrl(nodeId, versionId)}
      className="inline-flex h-[26px] shrink-0 items-center rounded-[6px] px-2 text-12 font-medium whitespace-nowrap text-text-2 no-underline hover:bg-subtle hover:text-text"
    >
      {t("pdf.download")}
    </a>
  );
}
