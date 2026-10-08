import { expect, test } from '@playwright/test';

test('displays the service versions returned by the API', async ({ page }) => {
  const requests: unknown[] = [];
  await page.route('**/api/service-versions', (route) => {
    requests.push(route.request().postDataJSON());
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify([{ id: '1', name: 'service.26.4.1' }])
    });
  });

  await page.goto('/');

  await expect(
    page.getByRole('heading', { name: 'Service versions without a release date' })
  ).toBeVisible();
  await page.getByLabel('Project key').fill('ABC');
  await page.getByLabel('Deployment version').fill('Deploy.ai-data.26.4.1');
  await page.getByRole('button', { name: 'Load report' }).click();
  await expect(page.getByText('service.26.4.1')).toBeVisible();
  await expect
    .poll(() => requests)
    .toEqual([{ project_key: 'ABC', release_version: 'Deploy.ai-data.26.4.1' }]);
});
