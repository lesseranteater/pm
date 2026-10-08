import { expect, test } from '@playwright/test';

test.skip(
  !process.env.PRODUCTION_BASE_URL,
  'Set PRODUCTION_BASE_URL for a live FastAPI smoke test'
);

test('displays the backend message', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Starter application' })).toBeVisible();
  await expect(page.getByText('Hello from the Python backend.')).toBeVisible();
});
