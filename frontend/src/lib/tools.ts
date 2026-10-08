export const tools = [
  {
    route: '/list-service-versions-without-a-release-date',
    title: 'List Service Versions Without a Release Date',
    summary:
      'Finds the service versions that still have no release date, for the issues assigned to a deployment version you choose.',
    access: 'Read only'
  },
  {
    route: '/release-a-semantic-version',
    title: 'Release a Semantic Version',
    summary:
      'Releases an unreleased deployment version in Jira, updates the Release State of its issues, comments on blocked parents and publishes the ones that are ready.',
    access: 'Changes Jira'
  },
  {
    route: '/archive-released-versions',
    title: 'Archive Released Versions',
    summary:
      'Archives every released version up to a date you pick, listing Semantic versions first and Service versions after.',
    access: 'Changes Jira'
  }
] as const;

export type ToolRoute = (typeof tools)[number]['route'];
