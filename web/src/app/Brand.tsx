import { Link } from "react-router-dom";
import { useI18n } from "../i18n";

export function Brand() {
  const { t } = useI18n();
  return (
    <span className="flex items-baseline gap-2">
      <Link to="/" className="text-[14px] font-semibold tracking-[-0.02em] text-text no-underline">
        {t("app.brand")}
      </Link>
      <span className="text-11 text-text-3">{t("app.brand.by")}</span>
    </span>
  );
}
