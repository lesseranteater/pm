import { expect, test } from '@playwright/test';

test('loads without running and archives only after the button is clicked', async ({ page }) => {
  const requests: unknown[] = [];
  await page.route('**/api/archive-released-versions', (route) => {
    requests.push(route.request().postDataJSON());
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        log: '2026-10-08 10:00:00,000 | INFO | Dry run: no changes were made.\n2026-10-08 10:00:01,000 | WARNING | Failed to archive v1'
      })
    });
  });
  await page.goto('/archive-released-versions');

  await expect(page.getByRole('heading', { name: 'Archive Released Versions' })).toBeVisible();
  await expect(page.getByRole('radio', { name: 'Yes' })).toBeChecked();
  await expect(page.getByLabel('Project Key')).toHaveValue('IGM');
  await expect(page.getByLabel('Archive Versions Released Up To')).not.toHaveValue('');
  expect(requests).toEqual([]);

  await page.getByLabel('Archive Versions Released Up To').fill('2026-09-30');
  await expect(page.getByRole('note')).toContainText(
    'on or before 30 September 2026 will be archived'
  );
  await expect(page.getByRole('note')).toContainText('Dry Run is on');
  await page.getByRole('radio', { name: 'No' }).check();
  await expect(page.getByRole('note')).toContainText('Dry Run is off');
  await page.getByRole('radio', { name: 'Yes' }).check();

  await page.getByRole('button', { name: 'Archive Versions' }).click();

  await expect(page.getByRole('log', { name: 'Script Log' })).toContainText('Dry run');
  await expect(page.locator('.log-warning')).toHaveCount(1);
  expect(requests).toEqual([{ project_key: 'IGM', archive_until: '2026-09-30', is_dry_run: true }]);
});

test('is reachable from the script dropdown', async ({ page }) => {
  await page.goto('/service-versions');

  await page.getByLabel('Script').selectOption('/archive-released-versions');
  await page.getByRole('button', { name: 'Load', exact: true }).click();

  await expect(page).toHaveURL(/\/archive-released-versions$/);
  await expect(page.getByRole('heading', { name: 'Archive Released Versions' })).toBeVisible();
});
