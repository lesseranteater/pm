<script lang="ts">
  import { onMount } from 'svelte';
  import VersionSelect from '$lib/VersionSelect.svelte';
  import ScriptLog from '$lib/ScriptLog.svelte';
  import { getServiceVersions } from '$lib/service-versions';
  import {
    getSemanticVersions,
    SemanticVersionsError,
    type VersionStatus
  } from '$lib/semantic-versions';

  const statusOptions: { value: VersionStatus; label: string }[] = [
    { value: 'unreleased', label: 'Unreleased' },
    { value: 'released', label: 'Released' },
    { value: 'archived', label: 'Archived' }
  ];

  let projectKey = $state('IGM');
  let status = $state<VersionStatus>('unreleased');
  let releaseVersion = $state('');
  let releaseVersions = $state<string[]>([]);
  let loadingVersions = $state(true);
  let log = $state('');
  let error = $state('');
  let pending = $state(false);
  let latestVersionsRequest = 0;

  const PROJECT_KEY_PATTERN = /^[A-Z][A-Z0-9_]{1,9}$/;

  async function loadReleaseVersions() {
    const request = ++latestVersionsRequest;
    error = '';
    loadingVersions = true;
    log = '';
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
        failure instanceof SemanticVersionsError && failure.status === 404
          ? `Jira project ${projectKey} was not found.`
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
    error = '';
    log = '';
    pending = true;
    try {
      log = await getServiceVersions(projectKey, releaseVersion);
    } catch {
      error = 'Unable to load service versions from the backend.';
    } finally {
      pending = false;
    }
  }
</script>

<svelte:head>
  <title>Service Versions Without a Release Date</title>
  <meta name="description" content="Jira service versions without a release date." />
</svelte:head>

<main>
  <section aria-labelledby="page-title">
    <h1 id="page-title">Service Versions Without a Release Date</h1>
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
      <button type="submit" disabled={pending || !releaseVersion}
        >{pending ? 'Loading...' : 'Load Report'}</button
      >
    </form>
    {#if error}
      <p class="error" role="alert">{error}</p>
    {/if}
    {#if log}
      <ScriptLog id="service-versions-log" {log} />
    {/if}
  </section>
</main>
