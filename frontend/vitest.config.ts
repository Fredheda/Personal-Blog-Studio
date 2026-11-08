import { defineConfig } from "vitest/config";

// Component tests run in jsdom; files that need Node (route handlers, file
// system checks) opt out with a `// @vitest-environment node` docblock.
export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["app/**/*.test.{ts,tsx}", "tests/**/*.test.ts"],
  },
});
