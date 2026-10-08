import { afterEach, expect, test, vi } from 'vitest';

import { parseLogLines, releaseSemanticVersion } from './release-semantic-version';

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

test('tags log lines with their level, including multi-line entries', () => {
  const log = [
    '2026-10-08 10:00:00,123 | INFO | Started',
    '2026-10-08 10:00:01,456 | WARNING | Blocked by:',
    'ABC-1',
    '2026-10-08 10:00:02,789 | INFO | Done'
  ].join('\n');

  expect(parseLogLines(log).map((line) => line.level)).toEqual([
    'INFO',
    'WARNING',
    'WARNING',
    'INFO'
  ]);
});
