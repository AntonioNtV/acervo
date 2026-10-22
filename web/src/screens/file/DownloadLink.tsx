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
        className="inline-flex h-7 shrink-0 cursor-pointer items-center gap-1.5 rounded-[6px] border-0 bg-transparent px-2 text-13 whitespace-nowrap text-text-2 no-underline hover:bg-subtle hover:text-text"
      >
        <svg viewBox="0 0 24 24" width={16} height={16} aria-hidden="true" className="shrink-0 fill-none stroke-current stroke-[1.5]">
          <path d="M12 4v12M6 10l6 6 6-6M5 20h14" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {t("file.download")}
      </button>
    </>
  );
}
