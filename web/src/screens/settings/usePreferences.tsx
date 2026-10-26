import { useEffect } from "react";
import { Outlet } from "react-router-dom";
import { useTheme } from "../../app/theme";
import { useMe, useSetPreferences, type Preferences } from "../../data/account";
import { useI18n, type Lang } from "../../i18n";

const langOf = (language: Preferences["language"]): Lang => (language === "en" ? "en" : "ptBR");

/** Changes preferences at once in this browser and on the account, so every device of the account gets them. */
export function usePreferences() {
  const { setTheme } = useTheme();
  const { setLang } = useI18n();
  const save = useSetPreferences();
  return (change: Partial<Preferences>) => {
    if (change.theme) setTheme(change.theme);
    if (change.language) setLang(langOf(change.language));
    save.mutate(change);
  };
}

/** Around every screen of the account: the account's theme and language win over what this browser last held. */
export function AccountPreferences() {
  const preferences = useMe().data?.preferences;
  const { setTheme } = useTheme();
  const { setLang } = useI18n();
  const theme = preferences?.theme;
  const language = preferences?.language;

  useEffect(() => {
    if (theme) setTheme(theme);
  }, [theme, setTheme]);
  useEffect(() => {
    if (language) setLang(langOf(language));
  }, [language, setLang]);

  return <Outlet />;
}
