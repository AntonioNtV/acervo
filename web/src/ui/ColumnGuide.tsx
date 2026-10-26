import { useI18n } from "../i18n";

/** The guide between two columns: invisible at rest, a 1 px line on hover. */
export function ColumnGuide() {
  const { t } = useI18n();
  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={t("media.columns.resize")}
      // The padding widens what the pointer can hover; bg-clip-content keeps the drawn line at 1 px.
      className="-mx-1 box-content w-px cursor-col-resize self-stretch bg-clip-content px-1 hover:bg-line-2"
    />
  );
}
