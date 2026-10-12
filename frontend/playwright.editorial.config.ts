import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e-editorial",
  workers: 1,
  retries: 0,
  reporter: [
    ["list"],
    [
      "html",
      {
        outputFolder: "../.artifacts/editorial-policy-ui/report",
        open: "never",
      },
    ],
  ],
  outputDir: "../.artifacts/editorial-policy-ui/test-results",
  use: {
    baseURL: "http://127.0.0.1:5192",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: "python ../scripts/ui_editorial_fixture_api.py",
      url: "http://127.0.0.1:5193/healthz",
      reuseExistingServer: false,
      timeout: 30000,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5192 --strictPort",
      url: "http://127.0.0.1:5192",
      reuseExistingServer: false,
      timeout: 30000,
      env: { NEWSFLOW_API_PROXY_TARGET: "http://127.0.0.1:5193" },
    },
  ],
});
