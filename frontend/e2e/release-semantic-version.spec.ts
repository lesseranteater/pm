import { expect, test } from '@playwright/test';

test('submits release parameters and displays the captured log', async ({ page }) => {
  await page.route('**/api/release-semantic-version', (route) => {
    expect(route.request().postDataJSON()).toEqual({
      version_name: 'Hotfix.ps-dev-1.26.4.3',
      is_dry_run: true
    });
    return route.fulfill({ contentType: 'application/json', body: '{"log":"DRY RUN complete"}' });
  });
  await page.goto('/release-semantic-version');

  await page.getByRole('radio', { name: 'Yes' }).check();
  await page.getByRole('button', { name: 'Release version' }).click();

  await expect(page.getByLabel('Release log')).toHaveValue('DRY RUN complete');
});
