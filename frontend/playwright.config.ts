import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [
    ["list"],
    [
      "html",
      { outputFolder: "../.artifacts/ui-dark-navy/report", open: "never" },
    ],
  ],
  outputDir: "../.artifacts/ui-dark-navy/test-results",
  use: {
    baseURL: "http://127.0.0.1:5180",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: "python ../scripts/ui_fixture_api.py",
      url: "http://127.0.0.1:5181/healthz",
      reuseExistingServer: false,
      timeout: 30000,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5180 --strictPort",
      url: "http://127.0.0.1:5180",
      reuseExistingServer: false,
      timeout: 30000,
      env: { NEWSFLOW_API_PROXY_TARGET: "http://127.0.0.1:5181" },
    },
  ],
});
