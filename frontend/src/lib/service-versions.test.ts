import { afterEach, expect, test, vi } from 'vitest';

import { getServiceVersions } from './service-versions';

afterEach(() => vi.unstubAllGlobals());

test('returns the report log from the backend', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"log":"Found 1 parent"}')));

  await expect(getServiceVersions('IGM', 'Deploy.ai-data.26.4.1')).resolves.toBe('Found 1 parent');
  expect(globalThis.fetch).toHaveBeenCalledWith('/api/service-versions', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ project_key: 'IGM', release_version: 'Deploy.ai-data.26.4.1' })
  });
});

test('rejects failed requests and invalid responses', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 503 })));
  await expect(getServiceVersions('IGM', 'Deploy.ai-data.26.4.1')).rejects.toThrow('failed');

  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('[{"name":"service"}]')));
  await expect(getServiceVersions('IGM', 'Deploy.ai-data.26.4.1')).rejects.toThrow('invalid');
});
