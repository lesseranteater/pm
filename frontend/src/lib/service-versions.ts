export async function getServiceVersions(
  projectKey: string,
  releaseVersion: string
): Promise<string> {
  const response = await globalThis.fetch('/api/service-versions', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ project_key: projectKey, release_version: releaseVersion })
  });
  if (!response.ok) throw new Error('Service version request failed');

  const body = (await response.json()) as { log?: unknown };
  if (typeof body.log !== 'string') throw new Error('Service version response is invalid');
  return body.log;
}
