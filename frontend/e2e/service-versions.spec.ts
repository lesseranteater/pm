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
      body: JSON.stringify([{ id: '1', name: 'service.26.4.1' }])
    });
  });

  await page.goto('/service-versions');

  await expect(
    page.getByRole('heading', { name: 'Service Versions Without a Release Date' })
  ).toBeVisible();
  await expect(page.getByRole('radio', { name: 'Unreleased' })).toBeChecked();
  await expect(page.getByRole('combobox', { name: 'Deployment Version' })).toHaveText(
    'Deploy.ai-data.26.4.1'
  );

  await page.getByLabel('Project Key').fill('ABC');
  await page.getByRole('radio', { name: 'Archived' }).check();
  await expect(page.getByRole('combobox', { name: 'Deployment Version' })).toHaveText(
    'Deploy.fe-dev.26.2.1'
  );
  await page.getByRole('radio', { name: 'Released' }).check();
  await expect(page.getByRole('combobox', { name: 'Deployment Version' })).toHaveText(
    'Deploy.fe-dev.26.3.6'
  );

  await page.getByRole('button', { name: 'Load Report' }).click();
  await expect(page.getByText('service.26.4.1')).toBeVisible();
  await expect
    .poll(() => requests)
    .toEqual([{ project_key: 'ABC', release_version: 'Deploy.fe-dev.26.3.6' }]);
});
