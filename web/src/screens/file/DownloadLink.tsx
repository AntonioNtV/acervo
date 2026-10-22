import { useErrorText } from "../../app/errors";
import { useDownloadFile } from "../../data/files";
import { useI18n } from "../../i18n";

/** "Baixar": asks the API for a signed link, which a plain link could not, and opens it. */
export function DownloadLink({ nodeId, filename, versionId }: { nodeId: string; filename: string; versionId?: string }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const download = useDownloadFile(nodeId, filename);
  return (
    <>
      {download.isError && <span className="px-1 text-12 text-err">{errorText(download.error)}</span>}
      <button
        type="button"
        disabled={download.isPending}
        onClick={() => download.mutate(versionId)}
        className="inline-flex h-[26px] shrink-0 cursor-pointer items-center rounded-[6px] border-0 bg-transparent px-2 text-12 font-medium whitespace-nowrap text-text-2 no-underline hover:bg-subtle hover:text-text"
      >
        {t("file.download")}
      </button>
    </>
  );
}
