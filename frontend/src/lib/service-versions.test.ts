import { afterEach, expect, test, vi } from 'vitest';

import { getServiceVersions } from './service-versions';

afterEach(() => vi.unstubAllGlobals());

test('streams the report log from the backend', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Found 1 parent')));
  let log = '';

  await getServiceVersions('IGM', 'Deploy.ai-data.26.4.1', (text) => (log += text));

  expect(log).toBe('Found 1 parent');
  expect(globalThis.fetch).toHaveBeenCalledWith('/api/service-versions', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ project_key: 'IGM', release_version: 'Deploy.ai-data.26.4.1' })
  });
});

test('rejects failed requests', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 503 })));

  await expect(getServiceVersions('IGM', 'Deploy.ai-data.26.4.1', () => {})).rejects.toThrow(
    'failed'
  );
});
