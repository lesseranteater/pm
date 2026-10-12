import { expect, test } from 'vitest';

import { countLevels, filterLines, parseLogLines, plural } from './script-log';

const log = [
  '2026-10-08 10:00:00,123 | INFO | Started',
  '2026-10-08 10:00:01,456 | WARNING | Blocked by:',
  'ABC-1',
  '2026-10-08 10:00:02,789 | ERROR | Something broke',
  '2026-10-08 10:00:03,000 | INFO | Done'
].join('\n');

test('tags log lines with their level, including multi-line entries', () => {
  expect(parseLogLines(log).map((line) => line.level)).toEqual([
    'INFO',
    'WARNING',
    'WARNING',
    'ERROR',
    'INFO'
  ]);
});

test('does not render the newline that ends a log as an extra blank line', () => {
  expect(parseLogLines(`${log}\n`)).toHaveLength(5);
  expect(parseLogLines('')).toHaveLength(1);
});

test('counts entries, warnings and errors', () => {
  expect(countLevels(log)).toEqual({ entries: 4, warnings: 1, errors: 1 });
  expect(countLevels('')).toEqual({ entries: 0, warnings: 0, errors: 0 });
});

test('filters by search text and by problems only', () => {
  const lines = parseLogLines(log);

  expect(filterLines(lines, { search: '', problemsOnly: false })).toHaveLength(5);
  expect(filterLines(lines, { search: 'done', problemsOnly: false }).map((l) => l.text)).toEqual([
    '2026-10-08 10:00:03,000 | INFO | Done'
  ]);
  // A continuation line stays with its warning, so it counts as a problem line too.
  expect(filterLines(lines, { search: '', problemsOnly: true })).toHaveLength(3);
  expect(filterLines(lines, { search: 'abc-1', problemsOnly: true })).toHaveLength(1);
});

test('pluralizes counts', () => {
  expect(plural(1, 'warning')).toBe('1 warning');
  expect(plural(2, 'warning')).toBe('2 warnings');
  expect(plural(0, 'log entry', 'log entries')).toBe('0 log entries');
});
