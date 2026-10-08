import { expect, test } from 'vitest';

import { addDays, formatDateInputValue, toDateInputValue } from './dates';

test('formats a local date as a date input value', () => {
  expect(toDateInputValue(new Date(2026, 0, 5))).toBe('2026-01-05');
  expect(toDateInputValue(new Date(2026, 11, 31))).toBe('2026-12-31');
});

test('adds days across month boundaries without mutating the input', () => {
  const from = new Date(2026, 9, 1);

  expect(toDateInputValue(addDays(from, -1))).toBe('2026-09-30');
  expect(toDateInputValue(from)).toBe('2026-10-01');
});

test('formats a date input value for display', () => {
  expect(formatDateInputValue('2026-10-08')).toBe('8 October 2026');
  expect(formatDateInputValue('')).toBe('');
  expect(formatDateInputValue('2026-02-31')).toBe('');
  expect(formatDateInputValue('not-a-date')).toBe('');
});
