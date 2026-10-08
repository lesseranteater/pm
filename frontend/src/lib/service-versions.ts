export type ServiceVersion = {
  id: string;
  name: string;
};

export async function getServiceVersions(
  projectKey: string,
  releaseVersion: string
): Promise<ServiceVersion[]> {
  const response = await globalThis.fetch('/api/service-versions', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ project_key: projectKey, release_version: releaseVersion })
  });
  if (!response.ok) throw new Error('Service version request failed');

  const body = (await response.json()) as unknown;
  if (!Array.isArray(body) || !body.every(isServiceVersion)) {
    throw new Error('Service version response is invalid');
  }
  return body;
}

function isServiceVersion(value: unknown): value is ServiceVersion {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as ServiceVersion).id === 'string' &&
    typeof (value as ServiceVersion).name === 'string'
  );
}
