import { useI18n } from "../../i18n";

export function BaseLayout() {
  const { t } = useI18n();
  return <h2 className="m-0 px-2.5 text-13 font-medium">{t("app.placeholder.base")}</h2>;
}
