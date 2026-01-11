import { defineConfig } from "@playwright/test";

const PORT = process.env.PORT || "3000";
const API_PORT = process.env.API_PORT || "8000";
const baseURL = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "./apps/web/e2e",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,

  // Auto-start backend and frontend servers before tests
  webServer: [
    {
      command: 'cd apps/api && uvicorn main:app --port 8000',
      port: 8000,
      timeout: 120 * 1000,
      reuseExistingServer: !process.env.CI,
      stdout: 'pipe',
    },
    {
      command: 'cd apps/web && npm run start', // Requires build first
      port: 3000,
      timeout: 120 * 1000,
      reuseExistingServer: !process.env.CI,
      stdout: 'pipe',
    }
  ],

  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    chromiumSandbox: false,
    launchOptions: {
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-seccomp-filter-sandbox"],
    },
  },
  projects: [
    { name: 'setup', testMatch: /.*\.setup\.ts/ },
    {
      name: 'chromium',
      use: {
        ...defineConfig({}).use,
        storageState: 'apps/web/.playwright/.auth/user.json',
      },
      dependencies: ['setup'],
    },
  ],
});
