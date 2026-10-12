export type LogLine = { text: string; level: string | null };

const LOG_ENTRY_START = /^\d{4}-\d{2}-\d{2} [\d:,]+ \| ([A-Z]+) \| /;

/** Tags each line with its log level; continuation lines inherit the level of their entry. */
export function parseLogLines(log: string): LogLine[] {
  let level: string | null = null;
  const lines = log.split('\n').map((text) => {
    level = LOG_ENTRY_START.exec(text)?.[1] ?? level;
    return { text, level };
  });
  // A log ends with a newline, which would otherwise render as a blank last line.
  if (lines.length > 1 && lines[lines.length - 1].text === '') lines.pop();
  return lines;
}

export type LogCounts = { entries: number; warnings: number; errors: number };

export function countLevels(log: string): LogCounts {
  const counts: LogCounts = { entries: 0, warnings: 0, errors: 0 };
  for (const line of log.split('\n')) {
    const level = LOG_ENTRY_START.exec(line)?.[1];
    if (!level) continue;
    counts.entries += 1;
    if (level === 'WARNING') counts.warnings += 1;
    if (level === 'ERROR' || level === 'CRITICAL') counts.errors += 1;
  }
  return counts;
}

/**
 * Parses a log as it streams in, so each chunk costs only its own lines rather than a rescan of
 * the whole log. A line is counted once it is complete; `flush` completes a trailing partial one.
 */
export class LogTracker {
  lines: LogLine[] = [];
  counts: LogCounts = { entries: 0, warnings: 0, errors: 0 };
  #level: string | null = null;
  #partial = '';

  append(text: string): void {
    const parts = (this.#partial + text).split('\n');
    this.#partial = parts.pop() ?? '';
    for (const part of parts) this.#add(part);
  }

  flush(): void {
    if (this.#partial === '') return;
    this.#add(this.#partial);
    this.#partial = '';
  }

  #add(text: string): void {
    const level = LOG_ENTRY_START.exec(text)?.[1];
    if (level) {
      this.#level = level;
      this.counts.entries += 1;
      if (level === 'WARNING') this.counts.warnings += 1;
      if (level === 'ERROR' || level === 'CRITICAL') this.counts.errors += 1;
    }
    this.lines.push({ text, level: this.#level });
  }
}

export function isProblem(line: LogLine): boolean {
  return line.level === 'WARNING' || line.level === 'ERROR' || line.level === 'CRITICAL';
}

/** Keeps the lines that match the search text and, optionally, only warnings and errors. */
export function filterLines(
  lines: LogLine[],
  options: { search: string; problemsOnly: boolean }
): LogLine[] {
  const needle = options.search.trim().toLowerCase();
  return lines.filter(
    (line) =>
      (!options.problemsOnly || isProblem(line)) &&
      (!needle || line.text.toLowerCase().includes(needle))
  );
}

export function plural(count: number, singular: string, pluralForm = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}
