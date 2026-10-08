import { expect, test } from '@playwright/test';

test.skip(
  !process.env.PRODUCTION_BASE_URL,
  'Set PRODUCTION_BASE_URL for a live FastAPI smoke test'
);

test('displays service versions from FastAPI', async ({ page }) => {
  await page.goto('/');

  await expect(
    page.getByRole('heading', { name: 'Service versions without a release date' })
  ).toBeVisible();
  await expect(page.locator('li')).toHaveCount(2);
});
