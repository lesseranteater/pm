import { expect, test, type Page } from '@playwright/test';

const DRY_LOG = [
  '2026-10-08 10:00:00,000 | INFO | Project: IGM',
  '2026-10-08 10:00:00,100 | INFO | Found 3 version(s) to archive:',
  '2026-10-08 10:00:00,200 | INFO | Semantic (2):',
  '2026-10-08 10:00:00,300 | INFO | Service (1):',
  '2026-10-08 10:00:00,400 | INFO | Dry run: no changes were made.'
].join('\n');

const LIVE_LOG = [
  '2026-10-08 10:05:00,000 | INFO | Project: IGM',
  '2026-10-08 10:05:00,100 | WARNING | Failed to archive sport-fe-1.36.0: 403 Forbidden',
  '2026-10-08 10:05:00,200 | INFO | Archived 2 of 3 version(s).'
].join('\n');

function daysAgo(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() - days);
  const two = (value: number) => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${two(date.getMonth() + 1)}-${two(date.getDate())}`;
}

/** Mocks the archive endpoints and records every run request. */
async function mockArchive(page: Page) {
  const runs: { project_key: string; archive_until: string; is_dry_run: boolean }[] = [];
  const previews: string[] = [];

  await page.route('**/api/archive-released-versions/preview*', (route) => {
    previews.push(new URL(route.request().url()).searchParams.get('archive_until') ?? '');
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ count: 3, semantic: 2, service: 1 })
    });
  });
  await page.route('**/api/archive-released-versions', (route) => {
    const body = route.request().postDataJSON();
    runs.push(body);
    return route.fulfill({
      contentType: 'text/plain; charset=utf-8',
      body: body.is_dry_run ? DRY_LOG : LIVE_LOG
    });
  });

  return { runs, previews };
}

test('loads without running, previews the count and dry-runs on request', async ({ page }) => {
  const { runs } = await mockArchive(page);
  await page.goto('/archive-released-versions');

  await expect(page.getByRole('heading', { name: 'Archive Released Versions' })).toBeVisible();
  await expect(page.getByRole('radio', { name: 'Yes' })).toBeChecked();
  await expect(page.getByLabel('Project Key')).toHaveValue('IGM');
  await expect(page.getByLabel('Archive Versions Released Up To')).toHaveValue(daysAgo(1));
  await expect(page.getByText('3 versions', { exact: false }).first()).toBeVisible();
  await expect(page.getByText('would be archived (2 Semantic, 1 Service)')).toBeVisible();
  expect(runs).toEqual([]);

  await page.getByRole('button', { name: '30 days ago' }).click();
  await expect(page.getByLabel('Archive Versions Released Up To')).toHaveValue(daysAgo(30));
  await expect(page.getByRole('button', { name: '30 days ago' })).toHaveAttribute(
    'aria-pressed',
    'true'
  );
  await expect(page.getByRole('note')).toContainText('Dry Run is on');

  await page.getByRole('button', { name: 'Archive Versions', exact: true }).click();

  await expect(page.getByRole('log', { name: 'Script Log' })).toContainText('Found 3 version(s)');
  await expect(page.getByText('Finished in')).toBeVisible();
  await expect(page.getByText('3 versions: 2 Semantic, 1 Service.')).toBeVisible();
  expect(runs).toEqual([{ project_key: 'IGM', archive_until: daysAgo(30), is_dry_run: true }]);
});

test('a live run needs a matching dry run and a confirmation', async ({ page }) => {
  const { runs } = await mockArchive(page);
  await page.goto('/archive-released-versions');

  // No dry run yet, so the live button is locked and says why.
  await page.getByRole('radio', { name: 'No' }).check();
  await expect(page.getByRole('button', { name: 'Archive Versions (Live)' })).toBeDisabled();
  await expect(page.getByText('Run a dry run with these settings first.')).toBeVisible();
  await page.getByRole('radio', { name: 'Yes' }).check();

  await page.getByRole('button', { name: 'Archive Versions', exact: true }).click();
  await expect(page.getByText('Dry run finished with no errors.')).toBeVisible();

  // Apply, then change your mind: back to a dry run, nothing live sent.
  await page.getByRole('button', { name: 'Apply These Changes' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText('Archive 3 versions in IGM?');
  await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused();
  await dialog.getByRole('button', { name: 'Cancel' }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByRole('radio', { name: 'Yes' })).toBeChecked();
  expect(runs.filter((run) => !run.is_dry_run)).toEqual([]);

  // Apply and confirm: exactly one live run.
  await page.getByRole('button', { name: 'Apply These Changes' }).click();
  await dialog.getByRole('button', { name: 'Archive Versions (Live)' }).click();

  await expect(page.getByRole('log', { name: 'Script Log' })).toContainText('Archived 2 of 3');
  await expect(page.locator('.log-warning')).toHaveCount(1);
  expect(runs.filter((run) => !run.is_dry_run)).toHaveLength(1);

  // The live run used up the dry run: another one needs a fresh preview.
  await page.getByRole('radio', { name: 'No' }).check();
  await expect(page.getByRole('button', { name: 'Archive Versions (Live)' })).toBeDisabled();
});

test('changing the inputs after a run marks the log as out of date', async ({ page }) => {
  await mockArchive(page);
  await page.goto('/archive-released-versions');
  await page.getByRole('button', { name: 'Archive Versions', exact: true }).click();
  await expect(page.getByText('Finished in')).toBeVisible();

  await page.getByRole('button', { name: '90 days ago' }).click();

  await expect(page.getByText('The inputs have changed since this run')).toBeVisible();
  await expect(page.getByText('Apply These Changes')).toBeHidden();
});

test('the log can be searched and limited to warnings and errors', async ({ page }) => {
  await mockArchive(page);
  await page.goto('/archive-released-versions');
  await page.getByRole('radio', { name: 'No' }).check();
  await page.getByRole('radio', { name: 'Yes' }).check();
  await page.getByRole('button', { name: 'Archive Versions', exact: true }).click();
  await page.getByRole('button', { name: 'Apply These Changes' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Archive Versions (Live)' }).click();
  await expect(page.locator('.log-warning')).toHaveCount(1);

  await page.getByRole('checkbox', { name: 'Warnings and errors only' }).check();
  await expect(page.getByText('Showing 1 of 3 lines')).toBeVisible();

  await page.getByRole('checkbox', { name: 'Warnings and errors only' }).uncheck();
  await page.getByRole('searchbox', { name: 'Search the log' }).fill('archived 2');
  await expect(page.getByText('Showing 1 of 3 lines')).toBeVisible();
  await expect(page.getByRole('log', { name: 'Script Log' })).toContainText('Archived 2 of 3');
});

test('explains why a run failed', async ({ page }) => {
  await page.route('**/api/archive-released-versions/preview*', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: '{"detail":"Jira rejected the access token (HTTP 401)."}'
    })
  );
  await page.route('**/api/archive-released-versions', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: '{"detail":"Unable to archive released versions"}'
    })
  );
  await page.goto('/archive-released-versions');

  await expect(page.getByText('Jira rejected the access token (HTTP 401).')).toBeVisible();
  await page.getByRole('button', { name: 'Archive Versions', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Unable to archive released versions');
});

test('is reachable from the tool dropdown', async ({ page }) => {
  await page.goto('/list-service-versions-without-a-release-date');

  await page.getByLabel('Select a Tool').selectOption('/archive-released-versions');

  await expect(page).toHaveURL(/\/archive-released-versions$/);
  await expect(page.getByRole('heading', { name: 'Archive Released Versions' })).toBeVisible();
});
