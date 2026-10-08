export async function releaseSemanticVersion(
  versionName: string,
  isDryRun: boolean
): Promise<string> {
  const response = await globalThis.fetch('/api/release-semantic-version', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ version_name: versionName, is_dry_run: isDryRun })
  });
  if (!response.ok) throw new Error('Release request failed');

  const body = (await response.json()) as { log?: unknown };
  if (typeof body.log !== 'string') throw new Error('Release response is invalid');
  return body.log;
}

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
