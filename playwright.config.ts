import { defineConfig } from "@playwright/test";

const PORT = process.env.PORT || "3000";
const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

export default defineConfig({
  testDir: "./apps/web/e2e",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    chromiumSandbox: false,
    launchOptions: {
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-seccomp-filter-sandbox"],
    },
  },
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : [["list"]],
  workers: 1,
});
