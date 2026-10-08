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
