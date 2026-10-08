import { expect, test, type Page } from '@playwright/test';

const VERSIONS = ['Hotfix.core-dev-1.26.3.4', 'Hotfix.ps-dev-1.26.4.3'];

const DRY_LOG = [
  '2026-10-08 10:00:00,000 | INFO | DRY RUN complete',
  '2026-10-08 10:00:01,000 | WARNING | Blocked'
].join('\n');

const LIVE_LOG = '2026-10-08 10:05:00,000 | INFO | Released Hotfix.ps-dev-1.26.4.3';

async function mockRelease(page: Page) {
  const runs: { version_name: string; is_dry_run: boolean }[] = [];

  await page.route('**/api/semantic-versions*', (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify(VERSIONS) })
  );
  await page.route('**/api/release-semantic-version', (route) => {
    const body = route.request().postDataJSON();
    runs.push(body);
    return route.fulfill({
      contentType: 'text/plain; charset=utf-8',
      body: body.is_dry_run ? DRY_LOG : LIVE_LOG
    });
  });

  return { runs };
}

async function chooseHotfix(page: Page) {
  await page.getByRole('combobox', { name: 'Unreleased Deployment Version' }).click();
  await page.getByRole('option', { name: 'Hotfix.ps-dev-1.26.4.3' }).click();
}

test('submits release parameters and streams the log', async ({ page }) => {
  const { runs } = await mockRelease(page);
  await page.goto('/release-a-deployment-version');

  await chooseHotfix(page);
  await expect(page.getByRole('radio', { name: 'Yes' })).toBeChecked();
  await expect(page.getByRole('note')).toContainText(
    'Hotfix.ps-dev-1.26.4.3 will be released in Jira'
  );
  await expect(page.getByRole('note')).toContainText('Dry Run is on');
  await page.getByRole('radio', { name: 'No' }).check();
  await expect(page.getByRole('note')).toContainText('Dry Run is off');
  await page.getByRole('radio', { name: 'Yes' }).check();
  await page.getByRole('button', { name: 'Release Version', exact: true }).click();

  await expect(page.getByRole('log', { name: 'Script Log' })).toContainText('DRY RUN complete');
  await expect(page.locator('.log-warning')).toHaveCount(1);
  await expect(page.locator('.log-warning')).toContainText('Blocked');
  expect(runs).toEqual([{ version_name: 'Hotfix.ps-dev-1.26.4.3', is_dry_run: true }]);
});

test('a live release needs a matching dry run and a confirmation', async ({ page }) => {
  const { runs } = await mockRelease(page);
  await page.goto('/release-a-deployment-version');
  await chooseHotfix(page);

  await page.getByRole('radio', { name: 'No' }).check();
  await expect(page.getByRole('button', { name: 'Release Version (Live)' })).toBeDisabled();
  await expect(page.getByText('Run a dry run with this version first.')).toBeVisible();
  await page.getByRole('radio', { name: 'Yes' }).check();

  await page.getByRole('button', { name: 'Release Version', exact: true }).click();
  await expect(page.getByText('Dry run finished with no errors.')).toBeVisible();

  await page.getByRole('button', { name: 'Apply These Changes' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText('Release Hotfix.ps-dev-1.26.4.3 in Jira?');
  await dialog.getByRole('button', { name: 'Cancel' }).click();
  await expect(page.getByRole('radio', { name: 'Yes' })).toBeChecked();
  expect(runs.filter((run) => !run.is_dry_run)).toEqual([]);

  await page.getByRole('button', { name: 'Apply These Changes' }).click();
  await dialog.getByRole('button', { name: 'Release Version (Live)' }).click();

  await expect(page.getByRole('log', { name: 'Script Log' })).toContainText(
    'Released Hotfix.ps-dev-1.26.4.3'
  );
  expect(runs.filter((run) => !run.is_dry_run)).toEqual([
    { version_name: 'Hotfix.ps-dev-1.26.4.3', is_dry_run: false }
  ]);
});

test('choosing another version after a dry run locks the live release again', async ({ page }) => {
  await mockRelease(page);
  await page.goto('/release-a-deployment-version');
  await chooseHotfix(page);
  await page.getByRole('button', { name: 'Release Version', exact: true }).click();
  await expect(page.getByText('Dry run finished with no errors.')).toBeVisible();

  await page.getByRole('combobox', { name: 'Unreleased Deployment Version' }).click();
  await page.getByRole('option', { name: 'Hotfix.core-dev-1.26.3.4' }).click();

  await expect(page.getByText('The inputs have changed since this run')).toBeVisible();
  await page.getByRole('radio', { name: 'No' }).check();
  await expect(page.getByRole('button', { name: 'Release Version (Live)' })).toBeDisabled();
});

test('filters the deployment versions with a fuzzy search as the user types', async ({ page }) => {
  await page.route('**/api/semantic-versions*', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify([
        'Config.core-dev-1.26.4.4',
        'Hotfix.core-dev-1.26.4.1',
        'Hotfix.ps-dev-1.26.4.2'
      ])
    })
  );
  await page.goto('/release-a-deployment-version');

  const deployment = page.getByRole('combobox', { name: 'Unreleased Deployment Version' });
  await deployment.click();
  await expect(page.getByRole('option')).toHaveCount(3);

  await page.keyboard.type('hfps');
  await expect(page.getByRole('option')).toHaveCount(1);

  await page.keyboard.press('Enter');
  await expect(deployment).toHaveValue('Hotfix.ps-dev-1.26.4.2');
  await expect(page.getByRole('listbox')).toBeHidden();
});

test('shows the reason when the versions cannot be loaded', async ({ page }) => {
  await page.route('**/api/semantic-versions*', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: '{"detail":"Could not reach Jira. Check your network or VPN connection and try again."}'
    })
  );
  await page.goto('/release-a-deployment-version');

  await expect(page.getByRole('alert')).toContainText('Could not reach Jira');
});
