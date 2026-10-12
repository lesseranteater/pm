import { afterEach, expect, test, vi } from 'vitest';

import { releaseSemanticVersion } from './release-semantic-version';

afterEach(() => vi.unstubAllGlobals());

test('submits the release parameters and streams the log', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Dry run complete')));
  let log = '';

  await releaseSemanticVersion('Hotfix.ps-dev-1.26.4.3', true, (text) => (log += text));

  expect(log).toBe('Dry run complete');
  expect(globalThis.fetch).toHaveBeenCalledWith('/api/release-semantic-version', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ version_name: 'Hotfix.ps-dev-1.26.4.3', is_dry_run: true })
  });
});
