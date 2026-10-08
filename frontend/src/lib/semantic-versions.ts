export const VERSION_STATUSES = ['unreleased', 'released', 'archived'] as const;

export type VersionStatus = (typeof VERSION_STATUSES)[number];

export class SemanticVersionsError extends Error {
  constructor(readonly status: number) {
    super(`Semantic versions request failed (${status})`);
  }
}

export async function getSemanticVersions(
  status: VersionStatus,
  projectKey?: string
): Promise<string[]> {
  const params = new URLSearchParams({ status });
  if (projectKey) params.set('project_key', projectKey);

  const response = await globalThis.fetch(`/api/semantic-versions?${params}`);
  if (!response.ok) throw new SemanticVersionsError(response.status);

  const body = (await response.json()) as unknown;
  if (!Array.isArray(body) || !body.every((name) => typeof name === 'string')) {
    throw new Error('Semantic versions response is invalid');
  }
  return body;
}
