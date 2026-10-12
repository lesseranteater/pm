import { test as base, expect } from '@playwright/test';

export const test = base.extend({
  page: async ({ page }, use) => {
    await page.route('**/api/auth/me', (route) =>
      route.fulfill({ contentType: 'application/json', body: '{"username":"test@example.com"}' })
    );
    await use(page);
  }
});

export { expect };
export type { Page } from '@playwright/test';
