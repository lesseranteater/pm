import { expect, test } from './fixtures';

test('switches themes and remembers the preference after refresh', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' });
  await page.route('**/api/health', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: '{"status":"ok","jira_configured":true}'
    })
  );
  await page.goto('/');
  await page.getByRole('button', { name: 'test@example.com' }).click();
  const toggle = page.getByRole('switch', { name: 'Dark theme' });
  await expect(toggle).not.toBeChecked();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  const lightBackground = await page
    .locator('section')
    .evaluate((element) => getComputedStyle(element).backgroundColor);

  await toggle.focus();
  await page.keyboard.press('Space');
  await expect(toggle).toBeChecked();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('section')).not.toHaveCSS('background-color', lightBackground);

  await page.reload();
  await page.getByRole('button', { name: 'test@example.com' }).click();
  await expect(toggle).toBeChecked();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await toggle.click();
  await expect(toggle).not.toBeChecked();
  await expect(page.locator('section')).toHaveCSS('background-color', lightBackground);
});
