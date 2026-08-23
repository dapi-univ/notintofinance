import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  reporter: "line",
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
  ],
  webServer: [
    {
      command: "uv run --project ../api uvicorn app.main:app --host 127.0.0.1 --port 8100",
      url: "http://127.0.0.1:8100/health",
      env: {
        ...process.env,
        APP_ENV: "test",
        CORS_ORIGINS: "http://127.0.0.1:3100",
        DATABASE_URL: "",
        MARKET_DATA_PROVIDER: "mock",
      },
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npm run build && npm run start -- --port 3100",
      url: "http://127.0.0.1:3100/app",
      env: {
        ...process.env,
        NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8100",
      },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
