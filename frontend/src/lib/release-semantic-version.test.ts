import { afterEach, expect, test, vi } from 'vitest';

import { releaseSemanticVersion } from './release-semantic-version';

afterEach(() => vi.unstubAllGlobals());

test('submits the release parameters and returns the log', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"log":"Dry run complete"}')));

  await expect(releaseSemanticVersion('Hotfix.ps-dev-1.26.4.3', true)).resolves.toBe(
    'Dry run complete'
  );
  expect(globalThis.fetch).toHaveBeenCalledWith('/api/release-semantic-version', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ version_name: 'Hotfix.ps-dev-1.26.4.3', is_dry_run: true })
  });
});
