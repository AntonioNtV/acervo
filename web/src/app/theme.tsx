import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useState, type ReactNode } from "react";

export type Theme = "light" | "dark";
/** What the person picked; "system" follows the device's light or dark, live. */
export type ThemeChoice = Theme | "system";

const STORAGE_KEY = "acervo.theme";

function readChoice(): ThemeChoice {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark" || saved === "system") return saved;
  } catch {
    // No storage: follow the system.
  }
  return "system";
}

const darkQuery = () => window.matchMedia?.("(prefers-color-scheme: dark)");

type ThemeState = { theme: Theme; choice: ThemeChoice; setTheme: (choice: ThemeChoice) => void };

const ThemeContext = createContext<ThemeState | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setChoice] = useState<ThemeChoice>(readChoice);
  const [deviceDark, setDeviceDark] = useState(() => darkQuery()?.matches ?? false);
  const theme: Theme = choice === "system" ? (deviceDark ? "dark" : "light") : choice;

  useEffect(() => {
    const query = darkQuery();
    if (!query) return;
    const onChange = () => setDeviceDark(query.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  useLayoutEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  const setTheme = useCallback((next: ThemeChoice) => {
    setChoice(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // The choice still holds for this session.
    }
  }, []);

  return <ThemeContext.Provider value={{ theme, choice, setTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme outside ThemeProvider");
  return ctx;
}
