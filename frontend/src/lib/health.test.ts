import { afterEach, expect, test, vi } from 'vitest';

import { getHealth } from './health';

afterEach(() => vi.unstubAllGlobals());

test('reports whether Jira is configured', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(new Response('{"status":"ok","jira_configured":false}'))
  );

  await expect(getHealth()).resolves.toEqual({ status: 'ok', jiraConfigured: false });
});

test('rejects an invalid response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"status":"ok"}')));

  await expect(getHealth()).rejects.toThrow('invalid');
});
