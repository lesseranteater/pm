import { expect, test } from '@playwright/test';

test('displays the service versions returned by the API', async ({ page }) => {
  await page.route('**/api/service-versions', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify([{ id: '1', name: 'service.26.4.1' }])
    })
  );

  await page.goto('/');

  await expect(
    page.getByRole('heading', { name: 'Service versions without a release date' })
  ).toBeVisible();
  await expect(page.getByText('service.26.4.1')).toBeVisible();
});
