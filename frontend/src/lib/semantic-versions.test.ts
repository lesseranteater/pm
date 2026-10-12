import { afterEach, expect, test, vi } from 'vitest';

import { getSemanticVersions } from './semantic-versions';
import { ApiError } from './stream';

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

test('exposes the status and the explanation when the request fails', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(
        new Response('{"detail":"Jira project ABC was not found"}', { status: 404 })
      )
  );

  const failure = await getSemanticVersions('unreleased', 'ABC').catch((error: unknown) => error);

  expect(failure).toBeInstanceOf(ApiError);
  expect((failure as ApiError).status).toBe(404);
  expect((failure as ApiError).detail).toBe('Jira project ABC was not found');
});
