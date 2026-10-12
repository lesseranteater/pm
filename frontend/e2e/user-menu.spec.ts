import { expect, test } from './fixtures';

test('opens account settings and dismisses with Escape or an outside click', async ({ page }) => {
  await page.route('**/api/health', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: '{"status":"ok","jira_configured":true}'
    })
  );
  await page.goto('/');
  const trigger = page.getByRole('button', { name: 'test@example.com' });
  const panel = page.getByRole('region', { name: 'Account settings' });
  await expect(trigger).toHaveAttribute('aria-expanded', 'false');
  await expect(page.getByRole('switch', { name: 'Dark theme' })).toBeHidden();
  await trigger.click();
  await expect(panel).toBeVisible();
  await expect(panel.getByText('test@example.com')).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Sign out' })).toBeVisible();
  await page.keyboard.press('Tab');
  await expect(panel.getByRole('switch', { name: 'Dark theme' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(panel).toBeHidden();
  await expect(trigger).toBeFocused();
  await trigger.click();
  await page.getByRole('heading', { level: 1, name: 'Release Management Tools' }).click();
  await expect(panel).toBeHidden();
  await expect(trigger).toHaveAttribute('aria-expanded', 'false');
});
