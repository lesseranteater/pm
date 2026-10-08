import { afterEach, expect, test, vi } from 'vitest';

import { getServiceVersions } from './service-versions';

afterEach(() => vi.unstubAllGlobals());

test('returns service versions from the backend', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(new Response('[{"id":"1","name":"service.26.4.1"}]'))
  );

  await expect(getServiceVersions()).resolves.toEqual([{ id: '1', name: 'service.26.4.1' }]);
});

test('rejects invalid responses', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"name":"service"}')));

  await expect(getServiceVersions()).rejects.toThrow('Service version response is invalid');
});
