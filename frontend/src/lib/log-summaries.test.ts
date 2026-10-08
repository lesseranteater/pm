import { expect, test } from 'vitest';

import { foundVersionCount, summarizeArchive, summarizeServiceVersions } from './log-summaries';

const stamp = '2026-10-08 21:40:36,645 | INFO | ';

test('summarizes an archive log', () => {
  const log = [
    `${stamp}Found 275 version(s) to archive:`,
    `${stamp}Semantic (146):`,
    `${stamp} - Config.core-dev-1.26.3.1 (id=1) releaseDate=2026-01-01`,
    `${stamp}Service (129):`
  ].join('\n');

  expect(foundVersionCount(log)).toBe(275);
  expect(summarizeArchive(log)).toBe('275 versions: 146 Semantic, 129 Service.');
});

test('summarizes an archive log with nothing to archive', () => {
  const log = `${stamp}No released versions on or before 2026-08-31 to archive.`;

  expect(foundVersionCount(log)).toBeNull();
  expect(summarizeArchive(log)).toBe('');
});

test('uses the singular for one version', () => {
  const log = `${stamp}Found 1 version(s) to archive:\n${stamp}Semantic (1):\n${stamp}Service (0):`;

  expect(summarizeArchive(log)).toBe('1 version: 1 Semantic, 0 Service.');
});

test('summarizes a service versions report', () => {
  const log = [
    `${stamp}Found 2 matching parent issue(s).`,
    `${stamp}Service versions without release date: 3`
  ].join('\n');

  expect(summarizeServiceVersions(log)).toBe(
    '3 service versions without a release date across 2 parent issues.'
  );
});

test('has no summary until the result is in the log', () => {
  expect(summarizeServiceVersions(`${stamp}Searching Jira for parents assigned to 'x'.`)).toBe('');
});
