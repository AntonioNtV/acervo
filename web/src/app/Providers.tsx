import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { ApiError } from "../data/request";
import { I18nProvider } from "../i18n";
import { ThemeProvider } from "./theme";

// A failed read is tried once more, unless what it read is gone or the session is: a 404 or a 401 never heals.
const retry = (failures: number, error: unknown) =>
  failures < 1 && !(error instanceof ApiError && (error.code === "not_found" || error.status === 401));

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({ defaultOptions: { queries: { retry } } }));
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <I18nProvider>{children}</I18nProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
