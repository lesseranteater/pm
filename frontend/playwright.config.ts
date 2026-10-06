import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: 'e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  reporter: 'list',
  use: {
    baseURL: process.env.BASE_URL ?? process.env.PRODUCTION_BASE_URL ?? 'http://127.0.0.1:4173',
    trace: 'on-first-retry',
    ...devices['Desktop Chrome']
  },
  webServer: {
    command: 'pnpm preview --host 127.0.0.1',
    port: 4173,
    reuseExistingServer: !process.env.CI
  }
});
