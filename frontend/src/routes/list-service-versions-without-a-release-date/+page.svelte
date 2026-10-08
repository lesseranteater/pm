<script lang="ts">
  import { onMount } from 'svelte';
  import { summarizeServiceVersions } from '$lib/log-summaries';
  import { ScriptRun } from '$lib/run.svelte';
  import ScriptLog from '$lib/ScriptLog.svelte';
  import { getServiceVersions } from '$lib/service-versions';
  import { getSemanticVersions, type VersionStatus } from '$lib/semantic-versions';
  import { ApiError } from '$lib/stream';
  import VersionSelect from '$lib/VersionSelect.svelte';

  const statusOptions: { value: VersionStatus; label: string }[] = [
    { value: 'unreleased', label: 'Unreleased' },
    { value: 'released', label: 'Released' },
    { value: 'archived', label: 'Archived' }
  ];

  const PROJECT_KEY_PATTERN = /^[A-Z][A-Z0-9_]{1,9}$/;

  const run = new ScriptRun();

  let projectKey = $state('IGM');
  let status = $state<VersionStatus>('unreleased');
  let releaseVersion = $state('');
  let releaseVersions = $state<string[]>([]);
  let loadingVersions = $state(true);
  let error = $state('');
  let latestVersionsRequest = 0;

  const signature = $derived(`${projectKey}|${releaseVersion}`);
  const stale = $derived(run.status !== 'idle' && run.signature !== signature);

  async function loadReleaseVersions() {
    const request = ++latestVersionsRequest;
    error = '';
    loadingVersions = true;
    if (!PROJECT_KEY_PATTERN.test(projectKey)) {
      releaseVersions = [];
      releaseVersion = '';
      error = 'Enter a valid project key, for example IGM.';
      loadingVersions = false;
      return;
    }
    try {
      const names = await getSemanticVersions(status, projectKey);
      if (request !== latestVersionsRequest) return;
      releaseVersions = names;
      releaseVersion = names[0] ?? '';
    } catch (failure) {
      if (request !== latestVersionsRequest) return;
      releaseVersions = [];
      releaseVersion = '';
      error =
        failure instanceof ApiError && failure.status === 404
          ? `Jira project ${projectKey} was not found.`
          : failure instanceof ApiError && failure.detail
            ? failure.detail
            : 'Unable to load deployment versions.';
    } finally {
      if (request === latestVersionsRequest) loadingVersions = false;
    }
  }

  // Refresh the deployment versions for the project key that was just entered.
  function applyProjectKey() {
    projectKey = projectKey.trim().toUpperCase();
    void loadReleaseVersions();
  }

  onMount(loadReleaseVersions);

  async function loadServiceVersions() {
    if (run.running || !releaseVersion) return;
    const key = projectKey;
    const version = releaseVersion;

    await run.start({ description: `${key}, ${version}`, signature, dryRun: false }, (onText) =>
      getServiceVersions(key, version, onText)
    );
  }
</script>

<svelte:head>
  <title>List Service Versions Without a Release Date</title>
  <meta name="description" content="Jira service versions without a release date." />
</svelte:head>

<svelte:window
  onbeforeunload={(event) => {
    if (run.running) event.preventDefault();
  }}
/>

<main>
  <section aria-labelledby="page-title">
    <h1 id="page-title">List Service Versions Without a Release Date</h1>
    <form
      onsubmit={(event) => {
        event.preventDefault();
        void loadServiceVersions();
      }}
    >
      <label for="project-key">Project Key</label>
      <input
        id="project-key"
        bind:value={projectKey}
        onchange={applyProjectKey}
        onkeydown={(event) => {
          if (event.key !== 'Enter') return;
          event.preventDefault();
          applyProjectKey();
        }}
        maxlength="10"
        required
      />
      <fieldset>
        <legend>Release Version Status</legend>
        {#each statusOptions as option (option.value)}
          <label>
            <input
              type="radio"
              name="release-version-status"
              value={option.value}
              bind:group={status}
              onchange={() => void loadReleaseVersions()}
            />
            {option.label}
            {#if option.value === status && !loadingVersions && !error}
              <span class="count">({releaseVersions.length})</span>
            {/if}
          </label>
        {/each}
      </fieldset>
      <label for="release-version">Deployment Version</label>
      <VersionSelect
        id="release-version"
        bind:value={releaseVersion}
        options={releaseVersions}
        disabled={loadingVersions}
        placeholder={loadingVersions ? 'Loading versions...' : `No ${status} versions`}
      />
      <p class="notice" role="note">
        {#if releaseVersion}
          The report searches {projectKey || 'the project'} for Story, Enabler, Bug and Config Change
          issues assigned to <strong>{releaseVersion}</strong>, then lists the service versions on
          their sub-tasks that have no release date.
        {:else}
          Choose a deployment version to see what the report will do.
        {/if}
        It only reads from Jira, so nothing is changed.
      </p>
      <button type="submit" disabled={run.running || !releaseVersion}
        >{run.running ? 'Loading...' : 'Load Report'}</button
      >
    </form>
    {#if error}
      <p class="error" role="alert">{error}</p>
    {/if}
    {#if run.error}
      <p class="error" role="alert">{run.error}</p>
    {/if}
    {#if run.status !== 'idle'}
      <ScriptLog
        id="service-versions-log"
        {run}
        {stale}
        filename="list-service-versions"
        summary={summarizeServiceVersions(run.log)}
      />
    {/if}
  </section>
</main>
