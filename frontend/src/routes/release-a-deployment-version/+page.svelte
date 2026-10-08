<script lang="ts">
  import { onMount } from 'svelte';
  import VersionSelect from '$lib/VersionSelect.svelte';
  import { releaseSemanticVersion } from '$lib/release-semantic-version';
  import ScriptLog from '$lib/ScriptLog.svelte';
  import { getSemanticVersions } from '$lib/semantic-versions';

  let versionName = $state('');
  let versionNames = $state<string[]>([]);
  let loadingVersions = $state(true);
  let dryRun = $state(true);
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
  <title>Release a Deployment Version</title>
  <meta name="description" content="Release a Jira deployment version." />
</svelte:head>

<main>
  <section aria-labelledby="page-title">
    <h1 id="page-title">Release a Deployment Version</h1>
    <form
      onsubmit={(event) => {
        event.preventDefault();
        void releaseVersion();
      }}
    >
      <label for="deployment-version">Unreleased Deployment Version</label>
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
      <p class="notice" class:notice-warning={!dryRun} role="note">
        {#if versionName}
          <strong>{versionName}</strong> will be released in Jira. The script also updates the Release
          State of the issues that carry it, comments on parent issues that are blocked, and publishes
          parent issues that are ready.
        {:else}
          Choose an unreleased deployment version to see what will happen.
        {/if}
        {#if dryRun}
          Dry Run is on, so nothing changes in Jira. The log lists the updates it would make.
        {:else}
          <strong>Dry Run is off: these changes will be applied in Jira.</strong>
        {/if}
      </p>
      <button type="submit" class:danger={!dryRun} disabled={pending || !versionName}
        >{pending ? 'Releasing...' : dryRun ? 'Release Version' : 'Release Version (Live)'}</button
      >
    </form>
    {#if error}
      <p class="error" role="alert">{error}</p>
    {/if}
    {#if log}
      <ScriptLog id="release-log" {log} />
    {/if}
  </section>
</main>
