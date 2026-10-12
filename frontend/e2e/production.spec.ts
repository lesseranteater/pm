import { expect, test } from '@playwright/test';

test.skip(
  !process.env.PRODUCTION_BASE_URL ||
    !process.env.TEST_AUTH_USERNAME ||
    !process.env.TEST_AUTH_PASSWORD ||
    !process.env.TEST_JIRA_TOKEN,
  'Set PRODUCTION_BASE_URL, TEST_AUTH_USERNAME and TEST_AUTH_PASSWORD for a live FastAPI smoke test'
);

test('displays service versions from FastAPI', async ({ page }) => {
  await page.goto('/list-service-versions-without-a-release-date');
  await page.getByLabel('Email').fill(process.env.TEST_AUTH_USERNAME!);
  await page.getByLabel('Password', { exact: true }).fill(process.env.TEST_AUTH_PASSWORD!);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByLabel('Jira Token', { exact: true }).fill(process.env.TEST_JIRA_TOKEN!);
  await page.getByRole('button', { name: 'Save Token' }).click();

  await expect(
    page.getByRole('heading', { name: 'List Service Versions Without a Release Date' })
  ).toBeVisible();
  await page.getByRole('button', { name: 'Load Report' }).click();
  await expect(page.getByRole('log', { name: 'Script Log' })).toContainText(
    'Service versions without release date'
  );
});
