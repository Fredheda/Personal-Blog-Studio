import { defineConfig } from "@playwright/test";

import { API_ORIGIN, API_PORT, MSI_ORIGIN, MSI_PORT, WEB_ORIGIN, WEB_PORT } from "./e2e/ports.ts";

// `npm run e2e` builds first; E2E_SKIP_BUILD=1 reuses a fresh `.next`.
const build = process.env.E2E_SKIP_BUILD ? "" : "npm run build && ";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.spec.ts",
  workers: 1,
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"]],
  expect: { timeout: 10_000 },
  use: { baseURL: WEB_ORIGIN, trace: "on-first-retry" },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  // Started one after another, in this order: the API needs Azurite up.
  webServer: [
    {
      name: "azurite",
      // The locked package's own bin (`npm run e2e:install` installs it).
      // In memory: nothing on disk, all data gone when the run ends.
      command: "./e2e/azurite/node_modules/.bin/azurite --silent --inMemoryPersistence --skipApiVersionCheck",
      // 403 without credentials still means "listening".
      url: "http://127.0.0.1:10000/devstoreaccount1?comp=list",
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      name: "token",
      // The flag silences Node's note that frontend/package.json has no "type".
      command: "node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON e2e/msi.ts",
      url: `${MSI_ORIGIN}/healthz`,
      env: { E2E_MSI_PORT: MSI_PORT },
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      name: "api",
      command: `poetry run uvicorn e2e_support.studio_app:app --host 127.0.0.1 --port ${API_PORT}`,
      cwd: "../backend",
      url: `${API_ORIGIN}/healthz`,
      env: { E2E_WEB_ORIGIN: WEB_ORIGIN },
      reuseExistingServer: false,
      timeout: 90_000,
    },
    {
      name: "web",
      command: `${build}npm run start -- --port ${WEB_PORT} --hostname 127.0.0.1`,
      url: `${WEB_ORIGIN}/healthz`,
      env: {
        STUDIO_API_URL: API_ORIGIN,
        AZURE_CLIENT_ID: "e2e",
        STUDIO_API_AUDIENCE: "api://e2e",
        IDENTITY_ENDPOINT: `${MSI_ORIGIN}/msi/token`,
        IDENTITY_HEADER: "e2e",
        NEXT_TELEMETRY_DISABLED: "1",
      },
      reuseExistingServer: false,
      timeout: 240_000,
    },
  ],
});
