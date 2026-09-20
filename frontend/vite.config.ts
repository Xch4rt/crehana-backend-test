/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The dev server is the development half of D-03: it proxies /api to the API on
// localhost:8000 exactly as the container's nginx proxies it to api:8000. Both
// halves exist so that no code path anywhere needs an absolute API URL - the
// client ships the relative base path `/api/v1` and nothing else, which is what
// makes CORS unnecessary and leaves src/taskmanager unmodified (ADR-107).
//
// `changeOrigin: false` on purpose: the API does not route on Host, and keeping
// the browser's own Host is one fewer difference between this proxy and nginx.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: false,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"],
    // No globals: every test imports describe / it / expect from vitest by
    // name, so a reader can tell where a symbol came from and tsc can too.
    globals: false,
    css: false,
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
