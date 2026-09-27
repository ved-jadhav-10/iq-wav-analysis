import { defineConfig, devices } from '@playwright/test'

const port = 8765
const ci = Boolean(process.env.CI)

// Runs against the real product: `sanket` serving the production build (run `npm run build` first).
export default defineConfig({
  testDir: 'e2e',
  forbidOnly: ci,
  reporter: ci ? 'github' : 'list',
  use: { baseURL: `http://127.0.0.1:${port}` },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `uv run sanket --port ${port}`,
    url: `http://127.0.0.1:${port}/api/v1/health`,
    reuseExistingServer: !ci,
  },
})
