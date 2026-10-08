import { expect, test } from 'vitest';

import { ScriptRun } from './run.svelte';
import { ApiError } from './stream';

const options = { description: 'Dry run, IGM', signature: 'IGM|2026-09-30', dryRun: true };
const stamp = '2026-10-08 10:00:00,000 | ';

test('collects the log as it streams and finishes as done', async () => {
  const run = new ScriptRun();
  const seen: string[] = [];

  await run.start(options, async (onText) => {
    onText(`${stamp}INFO | one\n`);
    seen.push(run.log);
    onText(`${stamp}INFO | two\n`);
  });

  expect(seen[0]).toBe(`${stamp}INFO | one\n`);
  expect(run.log).toBe(`${stamp}INFO | one\n${stamp}INFO | two\n`);
  expect(run.status).toBe('done');
  expect(run.succeeded).toBe(true);
  expect(run.description).toBe('Dry run, IGM');
  expect(run.signature).toBe('IGM|2026-09-30');
  expect(run.finishedAt).toBeGreaterThanOrEqual(run.startedAt);
});

test('is running while the script is, and ignores a second start', async () => {
  const run = new ScriptRun();
  let finish: () => void = () => {};
  const first = run.start(options, () => new Promise<void>((resolve) => (finish = resolve)));

  expect(run.running).toBe(true);
  await run.start(options, async () => {
    throw new Error('must not run');
  });
  expect(run.status).toBe('running');

  finish();
  await first;
  expect(run.running).toBe(false);
});

test('warnings are fine but errors in the log mean it did not succeed', async () => {
  const withWarning = new ScriptRun();
  await withWarning.start(options, async (onText) => onText(`${stamp}WARNING | careful\n`));
  expect(withWarning.succeeded).toBe(true);

  const withError = new ScriptRun();
  await withError.start(options, async (onText) => onText(`${stamp}ERROR | broke\n`));
  expect(withError.status).toBe('done');
  expect(withError.succeeded).toBe(false);
});

test('reports the explanation the server gave when the request fails', async () => {
  const run = new ScriptRun();

  await run.start(options, async () => {
    throw new ApiError(503, 'Jira rejected the access token (HTTP 401).');
  });

  expect(run.status).toBe('failed');
  expect(run.succeeded).toBe(false);
  expect(run.error).toBe('Jira rejected the access token (HTTP 401).');
});

test('explains a network failure and an unknown failure', async () => {
  const offline = new ScriptRun();
  await offline.start(options, async () => {
    throw new TypeError('Failed to fetch');
  });
  expect(offline.error).toContain('Could not reach the server');

  const unknown = new ScriptRun();
  await unknown.start(options, async () => {
    throw new Error('boom');
  });
  expect(unknown.error).toBe('Something went wrong while running the script.');
});

test('a new run clears the previous log and error', async () => {
  const run = new ScriptRun();
  await run.start(options, async () => {
    throw new ApiError(500, 'first failed');
  });

  await run.start({ ...options, dryRun: false }, async (onText) => onText(`${stamp}INFO | ok\n`));

  expect(run.error).toBe('');
  expect(run.log).toBe(`${stamp}INFO | ok\n`);
  expect(run.dryRun).toBe(false);
  expect(run.status).toBe('done');
});
