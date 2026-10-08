import { expect, test } from '@playwright/test';

test('executes the selected script route', async ({ page }) => {
  await page.route('**/api/service-versions', (route) =>
    route.fulfill({ contentType: 'application/json', body: '[]' })
  );
  await page.goto('/');

  await page.getByLabel('Script').selectOption('/release-semantic-version');
  await page.getByRole('button', { name: 'Load' }).click();

  await expect(page).toHaveURL(/\/release-semantic-version$/);
  await expect(page.getByRole('heading', { name: 'Release a semantic version' })).toBeVisible();
  await expect(page.getByText('This workflow will be available here soon.')).toBeVisible();
});
