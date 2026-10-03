import { expect, test, type Page } from '@playwright/test';

async function mockAuth(page: Page, initiallyAuthenticated: boolean) {
  let authenticated = initiallyAuthenticated;
  await page.route('**/api/auth/me', async (route) => {
    if (authenticated) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ username: 'user' })
      });
    } else {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: '{"detail":"Not authenticated"}'
      });
    }
  });
  await page.route('**/api/auth/login', async (route) => {
    authenticated = true;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ username: 'user' })
    });
  });
  await page.route('**/api/auth/logout', async (route) => {
    authenticated = false;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '{"logged_out":true}'
    });
  });
}

test('supports the core board workflow', async ({ page }) => {
  await mockAuth(page, true);
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
  await mockAuth(page, true);
  await page.goto('/');
  await page.getByRole('button', { name: 'Rename Review column' }).click();
  await page.locator('#rename-review').fill('Ready for review');
  await page.getByRole('button', { name: 'Save column name' }).click();
  await expect(page.getByRole('heading', { name: 'Ready for review' })).toBeVisible();
});

test('requires sign-in before showing the board', async ({ page }) => {
  await mockAuth(page, false);
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Welcome back.' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Make the next move.' })).not.toBeVisible();
  await page.getByLabel('Username').fill('user');
  await page.getByLabel('Password').fill('password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Make the next move.' })).toBeVisible();
});

test('can log out from the board', async ({ page }) => {
  await mockAuth(page, true);
  await page.goto('/');
  await page.getByRole('button', { name: 'Log out' }).click();
  await expect(page.getByRole('heading', { name: 'Welcome back.' })).toBeVisible();
});
