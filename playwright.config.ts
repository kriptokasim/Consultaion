import { defineConfig } from "@playwright/test";

const PORT = process.env.PORT || "3000";
const API_PORT = process.env.API_PORT || "8000";
const baseURL = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${PORT}`;
const chromiumExecutablePath =
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined;

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
      executablePath: chromiumExecutablePath,
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
    {
      name: 'mobile-chrome',
      use: {
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
        storageState: 'apps/web/.playwright/.auth/user.json',
      },
      dependencies: ['setup'],
    },
    {
      name: 'mobile-safari',
      use: {
        viewport: { width: 375, height: 667 },
        isMobile: true,
        hasTouch: true,
        storageState: 'apps/web/.playwright/.auth/user.json',
      },
      dependencies: ['setup'],
    },
  ],
});
