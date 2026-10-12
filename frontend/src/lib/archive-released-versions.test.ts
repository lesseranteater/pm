import { afterEach, expect, test, vi } from 'vitest';

import { archiveReleasedVersions, getArchivePreview } from './archive-released-versions';

afterEach(() => vi.unstubAllGlobals());

test('submits the project key, archive date and dry run choice and streams the log', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Dry run complete')));
  let log = '';

  await archiveReleasedVersions('IGM', '2026-09-30', true, (text) => (log += text));

  expect(log).toBe('Dry run complete');
  expect(globalThis.fetch).toHaveBeenCalledWith('/api/archive-released-versions', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ project_key: 'IGM', archive_until: '2026-09-30', is_dry_run: true })
  });
});

test('rejects a failed request', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 503 })));

  await expect(archiveReleasedVersions('IGM', '2026-09-30', true, () => {})).rejects.toThrow(
    'failed'
  );
});

test('requests the preview counts for a project and date', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(new Response('{"count":3,"semantic":2,"service":1}'))
  );

  await expect(getArchivePreview('IGM', '2026-09-30')).resolves.toEqual({
    count: 3,
    semantic: 2,
    service: 1
  });
  expect(globalThis.fetch).toHaveBeenCalledWith(
    '/api/archive-released-versions/preview?project_key=IGM&archive_until=2026-09-30'
  );
});

test('rejects an invalid preview response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"count":"many"}')));

  await expect(getArchivePreview('IGM', '2026-09-30')).rejects.toThrow('invalid');
});
