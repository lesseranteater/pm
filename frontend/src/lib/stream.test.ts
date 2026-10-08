import { afterEach, expect, test, vi } from 'vitest';

import { ApiError, getJson, postStream } from './stream';

afterEach(() => vi.unstubAllGlobals());

function streamOf(chunks: Uint8Array[], init?: ResponseInit): Response {
  return new Response(
    new ReadableStream({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(chunk);
        controller.close();
      }
    }),
    init
  );
}

test('hands each chunk of the response to the caller as it arrives', async () => {
  const encoder = new TextEncoder();
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(streamOf([encoder.encode('one\n'), encoder.encode('two\n')]))
  );
  const received: string[] = [];

  await postStream('/api/run', { a: 1 }, (text) => received.push(text));

  expect(received).toEqual(['one\n', 'two\n']);
  expect(globalThis.fetch).toHaveBeenCalledWith('/api/run', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ a: 1 })
  });
});

test('decodes characters that are split across chunks', async () => {
  const bytes = new TextEncoder().encode('a → b');
  // Cut inside the three-byte arrow.
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(streamOf([bytes.slice(0, 3), bytes.slice(3)])));
  let text = '';

  await postStream('/api/run', {}, (chunk) => (text += chunk));

  expect(text).toBe('a → b');
});

test('throws an error that carries the status and the explanation from the server', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(
        new Response('{"detail":"Jira project ABC was not found"}', { status: 404 })
      )
  );

  const failure = await postStream('/api/run', {}, () => {}).catch((error: unknown) => error);

  expect(failure).toBeInstanceOf(ApiError);
  expect((failure as ApiError).status).toBe(404);
  expect((failure as ApiError).detail).toBe('Jira project ABC was not found');
});

test('still reports the status when the error body is not JSON', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(new Response('<html>oops</html>', { status: 502 }))
  );

  const failure = await getJson('/api/thing').catch((error: unknown) => error);

  expect(failure).toBeInstanceOf(ApiError);
  expect((failure as ApiError).status).toBe(502);
  expect((failure as ApiError).detail).toBe('');
});

test('returns parsed JSON', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"ok":true}')));

  await expect(getJson('/api/thing')).resolves.toEqual({ ok: true });
});
