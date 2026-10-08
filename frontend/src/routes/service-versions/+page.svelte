<script lang="ts">
  import { onMount } from 'svelte';
  import VersionSelect from '$lib/VersionSelect.svelte';
  import { getServiceVersions, type ServiceVersion } from '$lib/service-versions';
  import { getSemanticVersions, type VersionStatus } from '$lib/semantic-versions';

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
  let versions = $state<ServiceVersion[] | null>(null);
  let error = $state('');
  let pending = $state(false);
  let latestVersionsRequest = 0;

  async function loadReleaseVersions() {
    const request = ++latestVersionsRequest;
    error = '';
    loadingVersions = true;
    versions = null;
    try {
      const names = await getSemanticVersions(status, projectKey);
      if (request !== latestVersionsRequest) return;
      releaseVersions = names;
      releaseVersion = names[0] ?? '';
    } catch {
      if (request !== latestVersionsRequest) return;
      releaseVersions = [];
      releaseVersion = '';
      error = 'Unable to load deployment versions.';
    } finally {
      if (request === latestVersionsRequest) loadingVersions = false;
    }
  }

  onMount(loadReleaseVersions);

  async function loadServiceVersions() {
    error = '';
    pending = true;
    try {
      versions = await getServiceVersions(projectKey, releaseVersion);
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
        onchange={() => void loadReleaseVersions()}
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
    {:else if pending && versions === null}
      <p aria-live="polite">Loading service versions...</p>
    {:else if versions?.length === 0}
      <p class="message">Every matching service version has a release date.</p>
    {:else if versions}
      <ul aria-live="polite">
        {#each versions as version (version.id)}
          <li>{version.name}</li>
        {/each}
      </ul>
    {/if}
  </section>
</main>
