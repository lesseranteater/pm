export type LogLine = { text: string; level: string | null };

const LOG_ENTRY_START = /^\d{4}-\d{2}-\d{2} [\d:,]+ \| ([A-Z]+) \| /;

/** Tags each line with its log level; continuation lines inherit the level of their entry. */
export function parseLogLines(log: string): LogLine[] {
  let level: string | null = null;
  return log.split('\n').map((text) => {
    level = LOG_ENTRY_START.exec(text)?.[1] ?? level;
    return { text, level };
  });
}
