export type ServiceVersion = {
  id: string;
  name: string;
};

export async function getServiceVersions(): Promise<ServiceVersion[]> {
  const response = await globalThis.fetch('/api/service-versions');
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
