import { expect, test } from '@playwright/test';

const versionsByStatus: Record<string, string[]> = {
  unreleased: ['Deploy.ai-data.26.4.1', 'Deploy.fe-dev.26.4.3'],
  released: ['Deploy.fe-dev.26.3.6'],
  archived: ['Deploy.fe-dev.26.2.1']
};

test('displays the service versions returned by the API', async ({ page }) => {
  const requests: unknown[] = [];
  await page.route('**/api/semantic-versions*', (route) => {
    const status = new URL(route.request().url()).searchParams.get('status') ?? '';
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(versionsByStatus[status])
    });
  });
  await page.route('**/api/service-versions', (route) => {
    requests.push(route.request().postDataJSON());
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        log: '2026-10-08 10:00:00,000 | INFO | Service versions without release date: 1\n2026-10-08 10:00:01,000 | WARNING | Check service.26.4.1'
      })
    });
  });

  await page.goto('/service-versions');

  await expect(
    page.getByRole('heading', { name: 'Service Versions Without a Release Date' })
  ).toBeVisible();
  await expect(page.getByRole('radio', { name: 'Unreleased' })).toBeChecked();
  await expect(page.getByText('(2)', { exact: true })).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Deployment Version' })).toHaveValue(
    'Deploy.ai-data.26.4.1'
  );

  await page.getByLabel('Project Key').fill('ABC');
  await page.getByRole('radio', { name: 'Archived' }).check();
  await expect(page.getByText('(1)', { exact: true })).toBeVisible();
  await expect(page.getByText('(2)', { exact: true })).toBeHidden();
  await expect(page.getByRole('combobox', { name: 'Deployment Version' })).toHaveValue(
    'Deploy.fe-dev.26.2.1'
  );
  await page.getByRole('radio', { name: 'Released' }).check();
  await expect(page.getByRole('combobox', { name: 'Deployment Version' })).toHaveValue(
    'Deploy.fe-dev.26.3.6'
  );

  const deployment = page.getByRole('combobox', { name: 'Deployment Version' });
  await deployment.click();
  await expect(page.getByRole('option')).toHaveCount(1);
  await deployment.fill('zzz');
  await expect(page.getByText('No matching versions').first()).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(deployment).toHaveValue('Deploy.fe-dev.26.3.6');

  await expect(page.getByRole('note')).toContainText('assigned to Deploy.fe-dev.26.3.6');
  await expect(page.getByRole('note')).toContainText('nothing is changed');

  await page.getByRole('button', { name: 'Load Report' }).click();
  await expect(page.getByRole('log', { name: 'Script Log' })).toContainText(
    'Service versions without release date: 1'
  );
  await expect(page.locator('.log-warning')).toHaveCount(1);
  await expect
    .poll(() => requests)
    .toEqual([{ project_key: 'ABC', release_version: 'Deploy.fe-dev.26.3.6' }]);
});

test('filters the deployment versions with a fuzzy search as the user types', async ({ page }) => {
  await page.route('**/api/semantic-versions*', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify([
        'Config.core-dev-1.26.4.4',
        'Deploy.fe-dev.26.4.3',
        'Deploy.fe-dev.26.3.6',
        'Hotfix.ps-dev-1.26.4.2'
      ])
    })
  );
  await page.goto('/service-versions');

  const deployment = page.getByRole('combobox', { name: 'Deployment Version' });
  await deployment.click();
  await expect(page.getByRole('option')).toHaveCount(4);

  await page.keyboard.type('dpfe');
  await expect(page.getByRole('option')).toHaveCount(2);

  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Enter');
  await expect(deployment).toHaveValue('Deploy.fe-dev.26.3.6');
  await expect(page.getByRole('listbox')).toBeHidden();
});
