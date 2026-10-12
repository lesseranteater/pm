import { expect, test } from '@playwright/test';

test('requires login, restores the session, and signs out', async ({ page }) => {
  let authenticated = false;
  let jiraConfigured = false;
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({
      status: authenticated ? 200 : 401,
      contentType: 'application/json',
      body: authenticated
        ? JSON.stringify({ username: 'alice@example.com', jira_configured: jiraConfigured })
        : '{"detail":"Not authenticated"}'
    })
  );
  await page.route('**/api/auth/login', (route) => {
    const input = route.request().postDataJSON();
    authenticated = input.username === 'alice@example.com' && input.password === 'correct';
    return route.fulfill({
      status: authenticated ? 200 : 401,
      contentType: 'application/json',
      body: authenticated
        ? '{"username":"alice@example.com"}'
        : '{"detail":"Invalid username or password"}'
    });
  });
  await page.route('**/api/auth/logout', (route) => {
    authenticated = false;
    jiraConfigured = false;
    return route.fulfill({ contentType: 'application/json', body: '{"logged_out":true}' });
  });
  await page.route('**/api/auth/jira-token', (route) => {
    expect(route.request().postDataJSON()).toEqual({ token: 'personal-jira-token' });
    jiraConfigured = true;
    return route.fulfill({ contentType: 'application/json', body: '{"jira_configured":true}' });
  });
  await page.route('**/api/health', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: '{"status":"ok","jira_configured":true}'
    })
  );
  await page.goto('/');
  await expect(page.getByLabel('Select a Tool')).toHaveCount(0);
  await expect(
    page.locator('.login-theme').getByRole('switch', { name: 'Dark theme' })
  ).toBeVisible();
  await page.getByLabel('Email').fill('alice@example.com');
  await page.getByLabel('Password', { exact: true }).fill('wrong');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Invalid username or password');
  await page.getByLabel('Password', { exact: true }).fill('correct');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Enter your Jira token' })).toBeVisible();
  await expect(page.getByLabel('Select a Tool')).toBeDisabled();
  await page.getByLabel('Jira Token', { exact: true }).fill('personal-jira-token');
  await page.getByRole('button', { name: 'Save Token' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('button', { name: 'alice@example.com' }).click();
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible();
  await expect(
    page.locator('.login-theme').getByRole('switch', { name: 'Dark theme' })
  ).toBeVisible();
});

test('returns to login when a tool request loses its session', async ({ page }) => {
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: '{"username":"alice@example.com","jira_configured":true}'
    })
  );
  await page.route('**/api/release-check', (route) =>
    route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: '{"detail":"Not authenticated"}'
    })
  );
  await page.goto('/release-check');
  await page.getByLabel('Deployment Plan Key').fill('IGM-123');
  await page.getByRole('button', { name: 'Run Check' }).click();
  await expect(page.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('Your session expired');
});

test('prompts again if the Jira cookie is missing and shows save failures', async ({ page }) => {
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: '{"username":"alice@example.com","jira_configured":true}'
    })
  );
  await page.route('**/api/release-check', (route) =>
    route.fulfill({
      status: 428,
      contentType: 'application/json',
      body: '{"detail":"Enter your Jira token to use this tool"}'
    })
  );
  await page.route('**/api/auth/jira-token', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: '{"detail":"Unavailable"}'
    })
  );
  await page.goto('/release-check');
  await page.getByLabel('Deployment Plan Key').fill('IGM-123');
  await page.getByRole('button', { name: 'Run Check' }).click();
  await expect(page.getByRole('dialog', { name: 'Enter your Jira token' })).toBeVisible();
  await page.getByLabel('Jira Token', { exact: true }).fill('personal-token');
  await page.getByRole('button', { name: 'Save Token' }).click();
  await expect(page.getByRole('dialog').getByRole('alert')).toContainText('Unable to save');
});

test('shows a plain message when the sign-in failure is not JSON', async ({ page }) => {
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: '{"detail":"Not authenticated"}'
    })
  );
  await page.route('**/api/auth/login', (route) =>
    route.fulfill({ status: 502, contentType: 'text/html', body: '<html>Bad Gateway</html>' })
  );

  await page.goto('/');
  await page.getByLabel('Email').fill('alice@example.com');
  await page.getByLabel('Password').fill('correct');
  await page.getByRole('button', { name: 'Sign in' }).click();

  await expect(page.getByRole('alert')).toHaveText('Unable to sign in.');
});
