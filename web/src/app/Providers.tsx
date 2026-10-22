import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { I18nProvider } from "../i18n";
import { ThemeProvider } from "./theme";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: 1 } } }));
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <I18nProvider>{children}</I18nProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
