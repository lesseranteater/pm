import { expect, test } from '@playwright/test';

test('submits release parameters and displays the captured log', async ({ page }) => {
  await page.route('**/api/semantic-versions*', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(['Hotfix.core-dev-1.26.3.4', 'Hotfix.ps-dev-1.26.4.3'])
    })
  );
  await page.route('**/api/release-semantic-version', (route) => {
    expect(route.request().postDataJSON()).toEqual({
      version_name: 'Hotfix.ps-dev-1.26.4.3',
      is_dry_run: true
    });
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        log: '2026-10-08 10:00:00,000 | INFO | DRY RUN complete\n2026-10-08 10:00:01,000 | WARNING | Blocked'
      })
    });
  });
  await page.goto('/release-semantic-version');

  await page.getByRole('combobox', { name: 'Unreleased Deployment Version' }).click();
  await page.getByRole('option', { name: 'Hotfix.ps-dev-1.26.4.3' }).click();
  await page.getByRole('radio', { name: 'Yes' }).check();
  await page.getByRole('button', { name: 'Release Version' }).click();

  await expect(page.getByRole('log', { name: 'Script Log' })).toContainText('DRY RUN complete');
  await expect(page.locator('.log-warning')).toHaveCount(1);
  await expect(page.locator('.log-warning')).toContainText('Blocked');
});

test('filters the deployment versions with a fuzzy search as the user types', async ({ page }) => {
  await page.route('**/api/semantic-versions*', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify([
        'Config.core-dev-1.26.4.4',
        'Hotfix.core-dev-1.26.4.1',
        'Hotfix.ps-dev-1.26.4.2'
      ])
    })
  );
  await page.goto('/release-semantic-version');

  const deployment = page.getByRole('combobox', { name: 'Unreleased Deployment Version' });
  await deployment.click();
  await expect(page.getByRole('option')).toHaveCount(3);

  await page.keyboard.type('hfps');
  await expect(page.getByRole('option')).toHaveCount(1);

  await page.keyboard.press('Enter');
  await expect(deployment).toHaveValue('Hotfix.ps-dev-1.26.4.2');
  await expect(page.getByRole('listbox')).toBeHidden();
});
