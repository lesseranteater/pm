import { expect, test } from 'vitest';

import { parseLogLines } from './script-log';

test('tags log lines with their level, including multi-line entries', () => {
  const log = [
    '2026-10-08 10:00:00,123 | INFO | Started',
    '2026-10-08 10:00:01,456 | WARNING | Blocked by:',
    'ABC-1',
    '2026-10-08 10:00:02,789 | INFO | Done'
  ].join('\n');

  expect(parseLogLines(log).map((line) => line.level)).toEqual([
    'INFO',
    'WARNING',
    'WARNING',
    'INFO'
  ]);
});
