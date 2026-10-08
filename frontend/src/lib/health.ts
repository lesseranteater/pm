import { getJson } from '$lib/stream';

export type Health = { status: string; jiraConfigured: boolean };

export async function getHealth(): Promise<Health> {
  const body = (await getJson('/api/health')) as { status?: unknown; jira_configured?: unknown };

  if (typeof body.status !== 'string' || typeof body.jira_configured !== 'boolean') {
    throw new Error('Health response is invalid');
  }
  return { status: body.status, jiraConfigured: body.jira_configured };
}
