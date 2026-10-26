import type { ReactNode } from "react";
import { useI18n } from "../i18n";
import { Icon } from "./Icon";
import { cx } from "./cx";

const linkButton = "cursor-pointer border-0 bg-transparent p-0 font-[inherit] text-[length:inherit] underline";

/**
 * A section shown from another page: flush with the page at rest; on hover or focus its frame, where it comes from and
 * "Editar na origem". When the source is gone (`error`), the notice and "Desvincular" in place of the content.
 */
export function SyncedFrame({
  source,
  error = false,
  onEdit,
  onUnlink,
  children,
}: {
  /** The page and section it comes from, e.g. "Renovação.md › Documentos". */
  source: string;
  error?: boolean;
  onEdit: () => void;
  onUnlink: () => void;
  children?: ReactNode;
}) {
  const { t } = useI18n();
  return (
    <div
      className={cx(
        "group/sync -m-px rounded-[6px] border",
        error
          ? "border-line-2 px-2.5 py-2"
          : "border-transparent focus-within:border-line-2 focus-within:px-2.5 focus-within:py-2 hover:border-line-2 hover:px-2.5 hover:py-2",
      )}
    >
      <div
        className={cx(
          "mb-1 flex items-center gap-1.5 text-12 text-text-3",
          !error && "sr-only group-focus-within/sync:not-sr-only group-hover/sync:not-sr-only",
        )}
      >
        <Icon name="link" size={14} />
        {t("media.synced.from", { source })}
        {!error && (
          <>
            {" · "}
            <button type="button" onClick={onEdit} className={cx(linkButton, "text-text-2")}>
              {t("media.synced.edit")}
            </button>
          </>
        )}
      </div>
      {error ? (
        <p role="alert" className="m-0 text-13 text-err">
          {t("media.synced.gone")}{" "}
          <button type="button" onClick={onUnlink} className={cx(linkButton, "text-err")}>
            {t("media.synced.unlink")}
          </button>{" "}
          {t("media.synced.keep")}
        </p>
      ) : (
        children
      )}
    </div>
  );
}
