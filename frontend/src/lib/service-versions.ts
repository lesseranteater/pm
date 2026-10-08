import { postStream } from '$lib/stream';

export function getServiceVersions(
  projectKey: string,
  releaseVersion: string,
  onText: (text: string) => void
): Promise<void> {
  return postStream(
    '/api/service-versions',
    { project_key: projectKey, release_version: releaseVersion },
    onText
  );
}
