import { defineConfig, devices } from "@playwright/test";

// E2E runs against the backend serving the built frontend (npm run build first).
// If Playwright's own browser can't be downloaded, set CHROME_PATH to a local Chrome.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: 0,
  use: {
    baseURL: "http://localhost:8000",
    ...devices["Pixel 7"],
    launchOptions: process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {},
  },
  webServer: {
    // The E2E run makes many calls per minute from one IP, so the rate limit is raised for tests only.
    command: "cd ../backend && RATE_LIMIT_PER_MIN=5000 python -m uvicorn app.main:app --port 8000",
    url: "http://localhost:8000/api/health",
    reuseExistingServer: true,
    timeout: 30_000,
  },
});
