import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

// Component tests run in jsdom; files that need Node (route handlers, file
// system checks) opt out with a `// @vitest-environment node` docblock.
export default defineConfig({
  resolve: {
    alias: { "server-only": fileURLToPath(new URL("./tests/stubs/server-only.ts", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup-dom.ts"],
    include: [
      "app/**/*.test.{ts,tsx}",
      "lib/**/*.test.{ts,tsx}",
      "components/**/*.test.{ts,tsx}",
      "effects/**/*.test.{ts,tsx}",
      "tests/**/*.test.ts",
      "scripts/**/*.test.ts",
    ],
  },
});
