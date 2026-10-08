import { expect, test } from '@playwright/test';

test('the home page explains the app and links to every tool', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { level: 1, name: 'Release Tools' })).toBeVisible();
  await expect(page.getByText('One place to run the Jira release scripts')).toBeVisible();
  await expect(page.getByLabel('Select a Tool')).toHaveValue('');

  await expect(page.locator('.tool-card')).toHaveCount(3);
  await expect(page.getByRole('link', { name: /Archive Released Versions/ })).toBeVisible();
  await expect(page.getByText('Safe By Default')).toBeVisible();
});

test('a tool card opens its tool and the logo returns home', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('link', { name: /Release a Semantic Version/ }).click();
  await expect(page).toHaveURL(/\/release-a-semantic-version$/);
  await expect(page.getByLabel('Select a Tool')).toHaveValue('/release-a-semantic-version');

  await page.getByRole('link', { name: 'Release Tools' }).first().click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByText('Safe By Default')).toBeVisible();
});
