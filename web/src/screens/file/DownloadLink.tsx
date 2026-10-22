import { downloadFile } from "../../data/files";
import { useI18n } from "../../i18n";

/** "Baixar": the bytes are fetched with the key, which a plain link could not send. */
export function DownloadLink({ nodeId, filename, versionId }: { nodeId: string; filename: string; versionId?: string }) {
  const { t } = useI18n();
  return (
    <button
      type="button"
      onClick={() => void downloadFile(nodeId, filename, versionId).catch(() => {})}
      className="inline-flex h-[26px] shrink-0 cursor-pointer items-center rounded-[6px] border-0 bg-transparent px-2 text-12 font-medium whitespace-nowrap text-text-2 no-underline hover:bg-subtle hover:text-text"
    >
      {t("file.download")}
    </button>
  );
}
