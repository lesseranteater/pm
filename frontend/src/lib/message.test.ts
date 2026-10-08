import { afterEach, expect, test, vi } from 'vitest';

import { getMessage } from './message';

afterEach(() => vi.unstubAllGlobals());

test('returns the backend message', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"message":"Hello"}')));

  await expect(getMessage()).resolves.toBe('Hello');
});

test('rejects unsuccessful responses', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 503 })));

  await expect(getMessage()).rejects.toThrow('Message request failed');
});
