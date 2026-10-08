import { expect, test } from 'vitest';

import { fuzzyFilter, highlightSegments } from './fuzzy';

const versions = [
  'Config.core-dev-1.26.4.4',
  'Deploy.core-dev-1.26.4.10',
  'Deploy.fe-dev.26.4.3',
  'Deploy.fe-dev.26.3.6',
  'Hotfix.ps-dev-1.26.4.2'
];

const names = (query: string) => fuzzyFilter(versions, query).map((match) => match.item);

test('an empty query returns every item in its original order', () => {
  expect(names('')).toEqual(versions);
  expect(names('   ')).toEqual(versions);
});

test('matches case-insensitively and in order, not necessarily adjacent', () => {
  expect(names('HOTFIX')).toEqual(['Hotfix.ps-dev-1.26.4.2']);
  expect(names('dpfe')).toEqual(['Deploy.fe-dev.26.4.3', 'Deploy.fe-dev.26.3.6']);
  expect(names('fed').slice(0, 2)).toEqual(['Deploy.fe-dev.26.4.3', 'Deploy.fe-dev.26.3.6']);
});

test('drops items that do not contain the query characters in order', () => {
  expect(names('xyz')).toEqual([]);
  expect(names('4.26')).toEqual([]);
});

test('requires every whitespace-separated token to match', () => {
  expect(names('fe 3.6')).toEqual(['Deploy.fe-dev.26.3.6']);
  expect(names('fe nothing')).toEqual([]);
});

test('ranks contiguous and word-start matches above scattered ones', () => {
  const results = fuzzyFilter(['Cosmic.red.ex', 'Deploy.core-dev-1'], 'core');

  expect(results.map((match) => match.item)).toEqual(['Deploy.core-dev-1', 'Cosmic.red.ex']);
});

test('reports the matched positions for highlighting', () => {
  const [match] = fuzzyFilter(['Deploy.fe-dev'], 'fe');

  expect(match.indices).toEqual([7, 8]);
  expect(highlightSegments('Deploy.fe-dev', match.indices)).toEqual([
    { text: 'Deploy.', match: false },
    { text: 'fe', match: true },
    { text: '-dev', match: false }
  ]);
});
