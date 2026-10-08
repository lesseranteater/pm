<script lang="ts">
  import { onMount } from 'svelte';
  import { getServiceVersions, type ServiceVersion } from '$lib/service-versions';

  let projectKey = $state('IGM');
  let releaseVersion = $state('Deploy.ai-data.26.4.1');
  let versions = $state<ServiceVersion[] | null>(null);
  let error = $state('');
  let pending = $state(false);

  onMount(() => {
    void loadServiceVersions();
  });

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
  <title>Service Versions</title>
  <meta name="description" content="Jira service versions without a release date." />
</svelte:head>

<main>
  <section aria-labelledby="page-title">
    <p class="eyebrow">Jira release report</p>
    <h1 id="page-title">Service versions without a release date</h1>
    <form
      onsubmit={(event) => {
        event.preventDefault();
        void loadServiceVersions();
      }}
    >
      <label for="project-key">Project key</label>
      <input id="project-key" bind:value={projectKey} maxlength="10" required />
      <label for="release-version">Release version</label>
      <input id="release-version" bind:value={releaseVersion} maxlength="120" required />
      <button type="submit" disabled={pending}>{pending ? 'Loading...' : 'Load report'}</button>
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
