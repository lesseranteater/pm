import { expect, test, type Page } from '@playwright/test';

async function mockAuth(page: Page, initiallyAuthenticated: boolean) {
  let authenticated = initiallyAuthenticated;
  const board = {
    id: 'board-mvp',
    name: 'Spring launch',
    columns: [
      {
        id: 'column-backlog',
        name: 'Backlog',
        position: 0,
        cards: [{ id: 'card-brief', title: 'Shape the product brief', details: '', position: 0 }]
      },
      { id: 'column-planned', name: 'Planned', position: 1, cards: [] },
      { id: 'column-progress', name: 'In progress', position: 2, cards: [] },
      { id: 'column-review', name: 'Review', position: 3, cards: [] },
      { id: 'column-done', name: 'Done', position: 4, cards: [] }
    ]
  };
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
  await page.route('**/api/board', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(board)
    });
  });
  await page.route('**/api/board/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const parts = url.pathname.split('/');
    if (request.method() === 'POST' && parts.at(-1) === 'cards') {
      const payload = JSON.parse(request.postData() ?? '{}') as {
        column_id: string;
        title: string;
        details: string;
      };
      board.columns
        .find((column) => column.id === payload.column_id)
        ?.cards.push({
          id: 'card-new',
          title: payload.title,
          details: payload.details,
          position: 99
        });
    }
    if (request.method() === 'PATCH' && parts.at(-2) === 'cards') {
      const payload = JSON.parse(request.postData() ?? '{}') as {
        title?: string;
        details?: string;
      };
      const card = board.columns
        .flatMap((column) => column.cards)
        .find((item) => item.id === parts.at(-1));
      if (card) Object.assign(card, payload);
    }
    if (request.method() === 'DELETE') {
      for (const column of board.columns)
        column.cards = column.cards.filter((card) => card.id !== parts.at(-1));
    }
    if (request.method() === 'POST' && parts.at(-3) === 'cards' && parts.at(-1) === 'move') {
      const payload = JSON.parse(request.postData() ?? '{}') as { column_id: string };
      const cardId = parts.at(-2);
      const source = board.columns.find((column) =>
        column.cards.some((card) => card.id === cardId)
      );
      const card = source?.cards.find((item) => item.id === cardId);
      if (source && card) {
        source.cards = source.cards.filter((item) => item.id !== cardId);
        board.columns.find((column) => column.id === payload.column_id)?.cards.push(card);
      }
    }
    if (request.method() === 'PATCH' && parts.at(-2) === 'columns') {
      const payload = JSON.parse(request.postData() ?? '{}') as { name: string };
      const column = board.columns.find((item) => item.id === parts.at(-1));
      if (column) column.name = payload.name;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(board)
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

  await page.getByLabel('Move Plan the launch well to').selectOption('column-done');
  const newCard = page.locator('.task-card').filter({ hasText: 'Plan the launch well' });
  await expect(newCard).toBeVisible();
  await newCard.getByRole('button', { name: 'Delete' }).click();
  await expect(page.getByRole('heading', { name: 'Plan the launch well' })).not.toBeVisible();
});

test('renames a column', async ({ page }) => {
  await mockAuth(page, true);
  await page.goto('/');
  await page.getByRole('button', { name: 'Rename Review column' }).click();
  await page.locator('#rename-column-review').fill('Ready for review');
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

test('reloads with mutations persisted by the API', async ({ page }) => {
  await mockAuth(page, true);
  await page.goto('/');
  await page.getByRole('button', { name: 'Add card' }).first().click();
  await page.getByLabel('Title').fill('Persisted from browser');
  await page.locator('form.new-card-form').getByRole('button', { name: 'Add card' }).click();
  await expect(page.getByRole('heading', { name: 'Persisted from browser' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Persisted from browser' })).toBeVisible();

  await page.getByRole('button', { name: 'Edit Persisted from browser' }).click();
  await page.getByLabel('Title').fill('Edited and persisted');
  await page.getByRole('button', { name: 'Save' }).click();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Edited and persisted' })).toBeVisible();

  await page.getByLabel('Move Edited and persisted to').selectOption('column-done');
  await page.reload();
  await expect(page.getByLabel('Move Edited and persisted to')).toHaveValue('column-done');

  await page.getByRole('button', { name: 'Rename Review column' }).click();
  await page.locator('#rename-column-review').fill('Ready for review');
  await page.getByRole('button', { name: 'Save column name' }).click();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Ready for review' })).toBeVisible();

  await page.getByRole('button', { name: 'Delete' }).last().click();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Edited and persisted' })).not.toBeVisible();
});

test('preserves a new-card draft when the API fails', async ({ page }) => {
  await mockAuth(page, true);
  await page.route('**/api/board/cards*', async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Board service unavailable' })
    });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Add card' }).first().click();
  await page.getByLabel('Title').fill('Keep this draft');
  await page.getByLabel('Details (optional)').fill('Do not lose these details');
  await page.locator('form.new-card-form').getByRole('button', { name: 'Add card' }).click();
  await expect(page.locator('input#new-title-column-backlog')).toHaveValue('Keep this draft');
  await expect(
    page.locator('p.login-error').filter({ hasText: 'Board service unavailable' })
  ).toBeVisible();
});
