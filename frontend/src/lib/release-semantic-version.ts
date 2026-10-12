import { postStream } from '$lib/stream';

export function releaseSemanticVersion(
  versionName: string,
  isDryRun: boolean,
  onText: (text: string) => void
): Promise<void> {
  return postStream(
    '/api/release-semantic-version',
    { version_name: versionName, is_dry_run: isDryRun },
    onText
  );
}
