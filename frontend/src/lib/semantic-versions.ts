import { getJson } from '$lib/stream';

export const VERSION_STATUSES = ['unreleased', 'released', 'archived'] as const;

export type VersionStatus = (typeof VERSION_STATUSES)[number];

export async function getSemanticVersions(
  status: VersionStatus,
  projectKey?: string
): Promise<string[]> {
  const params = new URLSearchParams({ status });
  if (projectKey) params.set('project_key', projectKey);

  const body = await getJson(`/api/semantic-versions?${params}`);
  if (!Array.isArray(body) || !body.every((name) => typeof name === 'string')) {
    throw new Error('Semantic versions response is invalid');
  }
  return body;
}
