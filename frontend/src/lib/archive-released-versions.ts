import { getJson, postStream } from '$lib/stream';

export type ArchivePreview = {
  count: number;
  semantic: number;
  service: number;
  eligible?: string[];
  unknown?: string[];
  unreleased?: string[];
  already_archived?: string[];
};

export function parseVersionNames(value: string): string[] {
  return [
    ...new Set(
      value
        .split(',')
        .map((name) => name.trim())
        .filter(Boolean)
    )
  ];
}

export function archiveReleasedVersions(
  projectKey: string,
  archiveUntil: string | string[],
  isDryRun: boolean,
  onText: (text: string) => void
): Promise<void> {
  return postStream(
    '/api/archive-released-versions',
    Array.isArray(archiveUntil)
      ? {
          project_key: projectKey,
          archive_by: 'versions',
          version_names: archiveUntil,
          is_dry_run: isDryRun
        }
      : { project_key: projectKey, archive_until: archiveUntil, is_dry_run: isDryRun },
    onText
  );
}

/** Preview a cutoff date or an exact list of names without changing Jira. */
export async function getArchivePreview(
  projectKey: string,
  archiveUntil: string | string[]
): Promise<ArchivePreview> {
  const byName = Array.isArray(archiveUntil);
  const url = '/api/archive-released-versions/preview';
  const body = (await (byName
    ? getJson(url, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ project_key: projectKey, version_names: archiveUntil })
      })
    : getJson(
        `${url}?${new URLSearchParams({ project_key: projectKey, archive_until: archiveUntil })}`
      ))) as Partial<ArchivePreview>;

  if (
    !body ||
    typeof body.count !== 'number' ||
    typeof body.semantic !== 'number' ||
    typeof body.service !== 'number'
  ) {
    throw new Error('Archive preview response is invalid');
  }
  if (byName) {
    for (const key of ['eligible', 'unknown', 'unreleased', 'already_archived'] as const) {
      if (!Array.isArray(body[key]) || !body[key].every((name) => typeof name === 'string')) {
        throw new Error('Archive preview response is invalid');
      }
    }
    return body as ArchivePreview;
  }
  return { count: body.count, semantic: body.semantic, service: body.service };
}
