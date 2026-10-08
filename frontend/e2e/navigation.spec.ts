import { expect, test } from '@playwright/test';

test('executes the selected script route', async ({ page }) => {
  await page.route('**/api/service-versions', (route) =>
    route.fulfill({ contentType: 'application/json', body: '[]' })
  );
  await page.goto('/service-versions');

  await page.getByLabel('Script').selectOption('/release-semantic-version');
  await page.getByRole('button', { name: 'Load', exact: true }).click();

  await expect(page).toHaveURL(/\/release-semantic-version$/);
  await expect(page.getByRole('heading', { name: 'Release a Semantic Version' })).toBeVisible();
  await expect(page.getByLabel('Unreleased Deployment Version')).toBeVisible();
});
