import { expect, test } from '@playwright/test';

test('runs a release check and displays its Script Log', async ({ page }) => {
  await page.route('**/api/release-check', (route) => {
    expect(route.request().postDataJSON()).toEqual({ deployment_plan_key: 'IGM-123' });
    return route.fulfill({
      contentType: 'text/plain; charset=utf-8',
      body: '2026-10-09 10:00:00,000 | INFO | CHECK COMPLETE'
    });
  });
  await page.goto('/release-check');

  await page.getByLabel('Deployment Plan Key').fill('igm-123');
  await page.getByRole('button', { name: 'Run Check' }).click();

  await expect(page.getByRole('log', { name: 'Script Log' })).toContainText('CHECK COMPLETE');
});
