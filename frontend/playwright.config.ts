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
    command: "cd ../backend && python -m uvicorn app.main:app --port 8000",
    url: "http://localhost:8000/api/health",
    reuseExistingServer: true,
    timeout: 30_000,
  },
});
