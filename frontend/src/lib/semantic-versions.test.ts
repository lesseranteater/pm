import { afterEach, expect, test, vi } from 'vitest';

import { getSemanticVersions } from './semantic-versions';

afterEach(() => vi.unstubAllGlobals());

test('requests the versions for the chosen status and project', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('["Deploy.fe-dev.26.4.3"]')));

  await expect(getSemanticVersions('archived', 'ABC')).resolves.toEqual(['Deploy.fe-dev.26.4.3']);
  expect(globalThis.fetch).toHaveBeenCalledWith(
    '/api/semantic-versions?status=archived&project_key=ABC'
  );
});

test('rejects an invalid response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"oops":1}')));

  await expect(getSemanticVersions('unreleased')).rejects.toThrow('invalid');
});
