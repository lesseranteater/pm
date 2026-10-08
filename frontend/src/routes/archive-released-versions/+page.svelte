<script lang="ts">
  import { archiveReleasedVersions } from '$lib/archive-released-versions';
  import { addDays, formatDateInputValue, toDateInputValue } from '$lib/dates';
  import ScriptLog from '$lib/ScriptLog.svelte';

  const PROJECT_KEY_PATTERN = /^[A-Z][A-Z0-9_]{1,9}$/;

  const today = toDateInputValue(new Date());

  let projectKey = $state('IGM');
  // Defaults to yesterday, so a run archives versions released before today.
  let archiveUntil = $state(toDateInputValue(addDays(new Date(), -1)));
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
    if (!formatDateInputValue(archiveUntil) || archiveUntil > today) {
      error = 'Choose a date that is not in the future.';
      return;
    }
    pending = true;
    try {
      log = await archiveReleasedVersions(projectKey, archiveUntil, dryRun);
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
      Archives every released version in the project up to the date you choose. Nothing runs until
      you click Archive Versions.
    </p>
    <form
      onsubmit={(event) => {
        event.preventDefault();
        void archiveVersions();
      }}
    >
      <label for="archive-project-key">Project Key</label>
      <input id="archive-project-key" bind:value={projectKey} maxlength="10" required />
      <label for="archive-until">Archive Versions Released Up To</label>
      <input id="archive-until" type="date" bind:value={archiveUntil} max={today} required />
      <fieldset>
        <legend>Dry Run</legend>
        <label><input type="radio" bind:group={dryRun} value={true} /> Yes</label>
        <label><input type="radio" bind:group={dryRun} value={false} /> No</label>
      </fieldset>
      <p class="notice" class:notice-warning={!dryRun} role="note">
        {#if formatDateInputValue(archiveUntil)}
          All released versions in {projectKey || 'the project'} with a release date on or before
          <strong>{formatDateInputValue(archiveUntil)}</strong> will be archived.
        {:else}
          Choose a date to see which versions will be archived.
        {/if}
        {#if dryRun}
          Dry Run is on, so nothing changes in Jira. The log lists the versions that would be
          archived.
        {:else}
          <strong>Dry Run is off: these versions will be archived in Jira.</strong>
        {/if}
      </p>
      <button type="submit" disabled={pending || !archiveUntil}
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
