<script lang="ts">
  import { onMount } from 'svelte';
  import { getServiceVersions, type ServiceVersion } from '$lib/service-versions';

  let versions = $state<ServiceVersion[] | null>(null);
  let error = $state('');

  onMount(() => {
    void loadServiceVersions();
  });

  async function loadServiceVersions() {
    error = '';
    try {
      versions = await getServiceVersions();
    } catch {
      error = 'Unable to load service versions from the backend.';
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
    {#if error}
      <p class="error" role="alert">{error}</p>
    {:else if versions === null}
      <p aria-live="polite">Loading service versions...</p>
    {:else if versions.length === 0}
      <p class="message">Every matching service version has a release date.</p>
    {:else}
      <ul aria-live="polite">
        {#each versions as version (version.id)}
          <li>{version.name}</li>
        {/each}
      </ul>
    {/if}
  </section>
</main>
