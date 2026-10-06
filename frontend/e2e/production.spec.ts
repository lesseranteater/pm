import { expect, test } from '@playwright/test';

test.skip(
  !process.env.PRODUCTION_BASE_URL,
  'Set PRODUCTION_BASE_URL for a live FastAPI smoke test'
);

test('persists a real board mutation through the production API', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Username').fill('user');
  await page.getByLabel('Password').fill('password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Make the next move.' })).toBeVisible();

  await page.getByRole('button', { name: 'Add card' }).first().click();
  await page.getByLabel('Title').fill('Container persistence check');
  await page.locator('form.new-card-form').getByRole('button', { name: 'Add card' }).click();
  await expect(page.getByRole('heading', { name: 'Container persistence check' })).toBeVisible();

  await page.reload();
  await expect(page.getByRole('heading', { name: 'Container persistence check' })).toBeVisible();
  await page
    .locator('.task-card')
    .filter({ hasText: 'Container persistence check' })
    .getByRole('button', { name: 'Delete' })
    .click();
  await expect(
    page.getByRole('heading', { name: 'Container persistence check' })
  ).not.toBeVisible();
});
