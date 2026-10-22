import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: "jsdom",
    globals: true,
    // The persistent module cache keeps i18n/index.ts transformed with its old import.meta.glob result, so a new
    // catalog file is not seen until the cache is wiped.
    fsModuleCache: false,
  },
});
