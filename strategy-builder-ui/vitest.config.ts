import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": resolve(__dirname, "./src") },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    // Pin the catch-all proxy's configuration so the suite reads the same
    // values whatever the developer's or CI runner's shell exports. The base
    // URL is the load-bearing one: src/app/api/[...path]/route.ts captures
    // `KIS_BUILDER_API_BASE` once at module load, so a test-local beforeEach
    // cannot undo an ambient value — it has already been read by the time the
    // first test runs. The PR that added the upstream-URL assertions documents
    // an e2e procedure that exports this variable at a container address, which
    // turned 13 of those assertions red on a developer shell. The two keys are
    // pinned empty for the same reason, one level cheaper: they are read per
    // request, so the suites that need a key set one themselves.
    env: {
      KIS_BUILDER_API_BASE: "http://localhost:5081",
      KIS_BUILDER_API_KEY: "",
      DASHBOARD_API_KEY: "",
    },
  },
});
