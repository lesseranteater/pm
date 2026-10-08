import { plural } from '$lib/script-log';

function numberAfter(log: string, pattern: RegExp): number | null {
  const match = pattern.exec(log);
  return match ? Number(match[1]) : null;
}

/** The number of versions an archive run found, from its log. */
export function foundVersionCount(log: string): number | null {
  return numberAfter(log, /\| Found (\d+) version\(s\) to archive/);
}

export function summarizeArchive(log: string): string {
  const found = foundVersionCount(log);
  if (found === null) return '';
  if (found === 0) return 'No versions to archive.';

  const semantic = numberAfter(log, /\| Semantic \((\d+)\):/) ?? 0;
  const service = numberAfter(log, /\| Service \((\d+)\):/) ?? 0;
  return `${plural(found, 'version')}: ${semantic} Semantic, ${service} Service.`;
}

export function summarizeServiceVersions(log: string): string {
  const missing = numberAfter(log, /\| Service versions without release date: (\d+)/);
  const parents = numberAfter(log, /\| Found (\d+) matching parent issue/);
  if (missing === null) return '';

  const parentText = parents === null ? '' : ` across ${plural(parents, 'parent issue')}`;
  return `${plural(missing, 'service version')} without a release date${parentText}.`;
}
