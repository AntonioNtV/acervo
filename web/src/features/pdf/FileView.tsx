import { useI18n } from "../../i18n";

export function FileView() {
  const { t } = useI18n();
  return <h1 className="m-0 text-32 font-medium tracking-[-0.035em]">{t("app.placeholder.file")}</h1>;
}
