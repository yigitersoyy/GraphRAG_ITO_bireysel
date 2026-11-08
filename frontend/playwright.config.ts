import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  timeout: 45000,
  expect: { timeout: 12000 },
  outputDir: "../reports/frontend-e2e",
  reporter: [
    ["list"],
    ["json", { outputFile: "../reports/frontend-e2e/results.json" }],
  ],
  use: {
    baseURL: process.env.WORKSPACE_TEST_URL || "http://127.0.0.1:18502",
    channel: process.platform === "win32" ? "msedge" : undefined,
    viewport: { width: 1440, height: 960 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
