import { useI18n } from "../../i18n";

export function PageView() {
  const { t } = useI18n();
  return <h1 className="m-0 text-32 font-medium tracking-[-0.035em]">{t("app.placeholder.page")}</h1>;
}
