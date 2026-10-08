import { expect, test } from '@playwright/test';

test('executes the selected script route', async ({ page }) => {
  await page.route('**/api/service-versions', (route) =>
    route.fulfill({ contentType: 'application/json', body: '[]' })
  );
  await page.goto('/list-service-versions-without-a-release-date');

  await page.getByLabel('Select a Tool').selectOption('/release-a-deployment-version');

  await expect(page).toHaveURL(/\/release-a-deployment-version$/);
  await expect(page.getByRole('heading', { name: 'Release a Deployment Version' })).toBeVisible();
  await expect(page.getByLabel('Unreleased Deployment Version')).toBeVisible();
});
