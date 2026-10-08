/** Formats a local date as YYYY-MM-DD, the value format of <input type="date">. */
export function toDateInputValue(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

/** The local date `days` days from `from` (negative for the past). */
export function addDays(from: Date, days: number): Date {
  const result = new Date(from.getFullYear(), from.getMonth(), from.getDate());
  result.setDate(result.getDate() + days);
  return result;
}

/** The last day of the month before `from`'s month. */
export function endOfLastMonth(from: Date): Date {
  return new Date(from.getFullYear(), from.getMonth(), 0);
}

/** A local timestamp that is safe in a file name, e.g. "20261008-214036". */
export function toFileStamp(date: Date): string {
  const two = (value: number) => String(value).padStart(2, '0');
  return (
    `${date.getFullYear()}${two(date.getMonth() + 1)}${two(date.getDate())}` +
    `-${two(date.getHours())}${two(date.getMinutes())}${two(date.getSeconds())}`
  );
}

/** Formats a YYYY-MM-DD value for display, e.g. "8 October 2026". Returns '' when invalid. */
export function formatDateInputValue(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return '';
  const [, year, month, day] = match.map(Number);
  const date = new Date(year, month - 1, day);
  if (date.getMonth() !== month - 1 || date.getDate() !== day) return '';
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
}
