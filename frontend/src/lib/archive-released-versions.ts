import { getJson, postStream } from '$lib/stream';

export type ArchivePreview = { count: number; semantic: number; service: number };

export function archiveReleasedVersions(
  projectKey: string,
  archiveUntil: string,
  isDryRun: boolean,
  onText: (text: string) => void
): Promise<void> {
  return postStream(
    '/api/archive-released-versions',
    { project_key: projectKey, archive_until: archiveUntil, is_dry_run: isDryRun },
    onText
  );
}

/** How many versions an archive run up to `archiveUntil` would touch. Changes nothing. */
export async function getArchivePreview(
  projectKey: string,
  archiveUntil: string
): Promise<ArchivePreview> {
  const params = new URLSearchParams({ project_key: projectKey, archive_until: archiveUntil });
  const body = (await getJson(
    `/api/archive-released-versions/preview?${params}`
  )) as Partial<ArchivePreview>;

  if (
    typeof body.count !== 'number' ||
    typeof body.semantic !== 'number' ||
    typeof body.service !== 'number'
  ) {
    throw new Error('Archive preview response is invalid');
  }
  return { count: body.count, semantic: body.semantic, service: body.service };
}
