<script lang="ts">
  import { onMount } from 'svelte';
  import VersionSelect from '$lib/VersionSelect.svelte';
  import { parseLogLines, releaseSemanticVersion } from '$lib/release-semantic-version';
  import { getSemanticVersions } from '$lib/semantic-versions';

  let versionName = $state('');
  let versionNames = $state<string[]>([]);
  let loadingVersions = $state(true);
  let dryRun = $state(false);
  let log = $state('');
  let error = $state('');
  let pending = $state(false);

  onMount(async () => {
    try {
      versionNames = await getSemanticVersions('unreleased');
      versionName = versionNames[0] ?? '';
    } catch {
      error = 'Unable to load unreleased deployment versions.';
    } finally {
      loadingVersions = false;
    }
  });

  async function releaseVersion() {
    error = '';
    log = '';
    pending = true;
    try {
      log = await releaseSemanticVersion(versionName, dryRun);
    } catch {
      error = 'Unable to release the deployment version.';
    } finally {
      pending = false;
    }
  }
</script>

<svelte:head>
  <title>Release a Semantic Version</title>
  <meta name="description" content="Release a Jira semantic version." />
</svelte:head>

<main>
  <section aria-labelledby="page-title">
    <h1 id="page-title">Release a Semantic Version</h1>
    <form
      onsubmit={(event) => {
        event.preventDefault();
        void releaseVersion();
      }}
    >
      <label for="deployment-version">Deployment Version</label>
      <VersionSelect
        id="deployment-version"
        bind:value={versionName}
        options={versionNames}
        disabled={loadingVersions}
        placeholder={loadingVersions ? 'Loading versions...' : 'No unreleased versions'}
      />
      <fieldset>
        <legend>Dry Run</legend>
        <label><input type="radio" bind:group={dryRun} value={true} /> Yes</label>
        <label><input type="radio" bind:group={dryRun} value={false} /> No</label>
      </fieldset>
      <button type="submit" disabled={pending || !versionName}
        >{pending ? 'Releasing...' : 'Release Version'}</button
      >
    </form>
    {#if error}
      <p class="error" role="alert">{error}</p>
    {/if}
    {#if log}
      <p id="release-log-label" class="log-label">Script Log</p>
      <pre
        id="release-log"
        class="release-log"
        role="log"
        aria-labelledby="release-log-label">{#each parseLogLines(log) as line, index (index)}<span
            class={line.level === 'WARNING' ? 'log-warning' : undefined}
            >{line.text}
</span>{/each}</pre>
    {/if}
  </section>
</main>
