export async function archiveReleasedVersions(
  projectKey: string,
  archiveUntil: string,
  isDryRun: boolean
): Promise<string> {
  const response = await globalThis.fetch('/api/archive-released-versions', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      project_key: projectKey,
      archive_until: archiveUntil,
      is_dry_run: isDryRun
    })
  });
  if (!response.ok) throw new Error('Archive request failed');

  const body = (await response.json()) as { log?: unknown };
  if (typeof body.log !== 'string') throw new Error('Archive response is invalid');
  return body.log;
}
