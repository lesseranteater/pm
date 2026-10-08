import { afterEach, expect, test, vi } from 'vitest';

import { archiveReleasedVersions } from './archive-released-versions';

afterEach(() => vi.unstubAllGlobals());

test('submits the project key, archive date and dry run choice and returns the log', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"log":"Dry run complete"}')));

  await expect(archiveReleasedVersions('IGM', '2026-09-30', true)).resolves.toBe(
    'Dry run complete'
  );
  expect(globalThis.fetch).toHaveBeenCalledWith('/api/archive-released-versions', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ project_key: 'IGM', archive_until: '2026-09-30', is_dry_run: true })
  });
});

test('rejects a failed request and an invalid response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 503 })));
  await expect(archiveReleasedVersions('IGM', '2026-09-30', true)).rejects.toThrow('failed');

  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"nope":1}')));
  await expect(archiveReleasedVersions('IGM', '2026-09-30', true)).rejects.toThrow('invalid');
});
