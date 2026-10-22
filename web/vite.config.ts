import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".");
  return {
    plugins: [react(), tailwindcss()],
    server: {
      proxy: { "/v1": { target: env.VITE_API_URL || "http://localhost:8000", changeOrigin: true } },
    },
    test: {
      environment: "jsdom",
      globals: true,
      // The persistent module cache keeps i18n/index.ts transformed with its old import.meta.glob result, so a new
      // catalog file is not seen until the cache is wiped.
      fsModuleCache: false,
    },
  };
});
