import { expect, test } from '@playwright/test';

test('displays the message returned by the API', async ({ page }) => {
  await page.route('**/api/message', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ message: 'Hello from the test backend.' })
    })
  );

  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Starter application' })).toBeVisible();
  await expect(page.getByText('Hello from the test backend.')).toBeVisible();
});
