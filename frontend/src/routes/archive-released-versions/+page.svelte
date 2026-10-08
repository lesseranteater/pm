<script lang="ts">
  import { archiveReleasedVersions } from '$lib/archive-released-versions';
  import ScriptLog from '$lib/ScriptLog.svelte';

  const PROJECT_KEY_PATTERN = /^[A-Z][A-Z0-9_]{1,9}$/;

  let projectKey = $state('IGM');
  let dryRun = $state(true);
  let log = $state('');
  let error = $state('');
  let pending = $state(false);

  async function archiveVersions() {
    projectKey = projectKey.trim().toUpperCase();
    error = '';
    log = '';
    if (!PROJECT_KEY_PATTERN.test(projectKey)) {
      error = 'Enter a valid project key, for example IGM.';
      return;
    }
    pending = true;
    try {
      log = await archiveReleasedVersions(projectKey, dryRun);
    } catch {
      error = 'Unable to archive the released versions.';
    } finally {
      pending = false;
    }
  }
</script>

<svelte:head>
  <title>Archive Released Versions</title>
  <meta name="description" content="Archive Jira versions that were released before today." />
</svelte:head>

<main>
  <section aria-labelledby="page-title">
    <h1 id="page-title">Archive Released Versions</h1>
    <p class="intro">
      Archives every released version in the project whose release date is before today. Nothing
      runs until you click Archive Versions.
    </p>
    <form
      onsubmit={(event) => {
        event.preventDefault();
        void archiveVersions();
      }}
    >
      <label for="archive-project-key">Project Key</label>
      <input id="archive-project-key" bind:value={projectKey} maxlength="10" required />
      <fieldset>
        <legend>Dry Run</legend>
        <label><input type="radio" bind:group={dryRun} value={true} /> Yes</label>
        <label><input type="radio" bind:group={dryRun} value={false} /> No</label>
      </fieldset>
      <button type="submit" disabled={pending}
        >{pending ? 'Archiving...' : 'Archive Versions'}</button
      >
    </form>
    {#if error}
      <p class="error" role="alert">{error}</p>
    {/if}
    {#if log}
      <ScriptLog id="archive-log" {log} />
    {/if}
  </section>
</main>
