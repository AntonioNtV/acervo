import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type Lang = "ptBR" | "en";
export type Messages = Record<string, string>;
export type Catalog = { ptBR: Messages; en: Messages };

const STORAGE_KEY = "acervo.lang";

// One `<screen>.ts` per screen, plus `app` and `errors`; its keys are reached as `t("<screen>.<key>")`.
const modules = import.meta.glob<Catalog>(["./*.ts", "!./index.ts", "!./*.test.ts"], { eager: true });

export const catalogs: Record<string, Catalog> = Object.fromEntries(
  Object.entries(modules).map(([path, mod]) => [path.slice(2, -3), mod]),
);

export function translate(lang: Lang, key: string, vars?: Record<string, string | number>): string {
  const dot = key.indexOf(".");
  const text = catalogs[key.slice(0, dot)]?.[lang][key.slice(dot + 1)] ?? key;
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (match, name: string) => (name in vars ? String(vars[name]) : match));
}

/** The BCP 47 tag that `Intl` and `toLocale*String` take for `lang`. */
export function locale(lang: Lang): "en" | "pt-BR" {
  return lang === "en" ? "en" : "pt-BR";
}

/** The browser's language, what the screens use before anyone signs in. */
export function browserLang(): Lang {
  return navigator.language.toLowerCase().startsWith("en") ? "en" : "ptBR";
}

function readLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved === "en" || saved === "ptBR" ? saved : browserLang();
  } catch {
    return browserLang();
  }
}

type I18n = {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
};

const I18nContext = createContext<I18n | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(readLang);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // The choice still holds for this session.
    }
  }, []);

  useLayoutEffect(() => {
    document.documentElement.lang = locale(lang);
  }, [lang]);

  const value = useMemo<I18n>(
    () => ({ lang, setLang, t: (key, vars) => translate(lang, key, vars) }),
    [lang, setLang],
  );
  return createElement(I18nContext.Provider, { value }, children);
}

export function useI18n(): I18n {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n outside I18nProvider");
  return ctx;
}
