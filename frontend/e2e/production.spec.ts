import { expect, test } from '@playwright/test';

test.skip(
  !process.env.PRODUCTION_BASE_URL,
  'Set PRODUCTION_BASE_URL for a live FastAPI smoke test'
);

test('displays service versions from FastAPI', async ({ page }) => {
  await page.goto('/service-versions');

  await expect(
    page.getByRole('heading', { name: 'List Service Versions Without a Release Date' })
  ).toBeVisible();
  await page.getByRole('button', { name: 'Load Report' }).click();
  await expect(page.getByRole('log', { name: 'Script Log' })).toContainText(
    'Service versions without release date'
  );
});
