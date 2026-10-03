import { expect, test } from '@playwright/test';

test('supports the core board workflow', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Make the next move.' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Backlog' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Done' })).toBeVisible();

  await page.getByRole('button', { name: 'Add card' }).first().click();
  await page.getByLabel('Title').fill('Plan the launch');
  await page.getByLabel('Details (optional)').fill('Confirm owners and dates');
  await page.locator('form.new-card-form').getByRole('button', { name: 'Add card' }).click();
  await expect(page.getByRole('heading', { name: 'Plan the launch' })).toBeVisible();

  await page.getByRole('button', { name: 'Edit Plan the launch' }).click();
  await page.getByLabel('Title').fill('Plan the launch well');
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('heading', { name: 'Plan the launch well' })).toBeVisible();

  await page.getByLabel('Move Plan the launch well to').selectOption('done');
  const newCard = page.locator('.task-card').filter({ hasText: 'Plan the launch well' });
  await expect(newCard).toBeVisible();
  await newCard.getByRole('button', { name: 'Delete' }).click();
  await expect(page.getByRole('heading', { name: 'Plan the launch well' })).not.toBeVisible();
});

test('renames a column', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Rename Review column' }).click();
  await page.locator('#rename-review').fill('Ready for review');
  await page.getByRole('button', { name: 'Save column name' }).click();
  await expect(page.getByRole('heading', { name: 'Ready for review' })).toBeVisible();
});
