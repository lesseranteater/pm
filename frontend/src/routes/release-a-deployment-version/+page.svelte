<script lang="ts">
  import { onMount } from 'svelte';
  import ConfirmDialog from '$lib/ConfirmDialog.svelte';
  import { releaseSemanticVersion } from '$lib/release-semantic-version';
  import { ScriptRun } from '$lib/run.svelte';
  import ScriptLog from '$lib/ScriptLog.svelte';
  import { getSemanticVersions } from '$lib/semantic-versions';
  import { ApiError } from '$lib/stream';
  import VersionSelect from '$lib/VersionSelect.svelte';

  const run = new ScriptRun();

  let versionName = $state('');
  let versionNames = $state<string[]>([]);
  let loadingVersions = $state(true);
  let dryRun = $state(true);
  let loadError = $state('');
  // The version of the last dry run that finished without errors. A live run needs a match.
  let verifiedVersion = $state('');
  let confirmOpen = $state(false);
  let openedFromShortcut = false;

  const canRunLive = $derived(versionName !== '' && verifiedVersion === versionName);
  const stale = $derived(run.status !== 'idle' && run.signature !== versionName);

  onMount(async () => {
    try {
      versionNames = await getSemanticVersions('unreleased');
      versionName = versionNames[0] ?? '';
    } catch (failure) {
      loadError =
        failure instanceof ApiError && failure.detail
          ? failure.detail
          : 'Unable to load unreleased deployment versions.';
    } finally {
      loadingVersions = false;
    }
  });

  async function execute(isDryRun: boolean) {
    const version = versionName;
    verifiedVersion = '';

    await run.start(
      {
        description: `${isDryRun ? 'Dry run' : 'Live run'}, ${version}`,
        signature: version,
        dryRun: isDryRun
      },
      (onText) => releaseSemanticVersion(version, isDryRun, onText)
    );

    // Only a dry run that finished cleanly unlocks the live run for this same version.
    verifiedVersion = isDryRun && run.succeeded ? version : '';
  }

  function submit() {
    if (run.running || !versionName) return;
    if (dryRun) {
      void execute(true);
    } else if (canRunLive) {
      openedFromShortcut = false;
      confirmOpen = true;
    }
  }

  function applyDryRun() {
    dryRun = false;
    openedFromShortcut = true;
    confirmOpen = true;
  }

  function cancelConfirm() {
    // Going back to a dry run keeps the safe choice selected after a change of mind.
    if (openedFromShortcut) dryRun = true;
    openedFromShortcut = false;
  }
</script>

<svelte:head>
  <title>Release a Deployment Version</title>
  <meta name="description" content="Release a Jira deployment version." />
</svelte:head>

<svelte:window
  onbeforeunload={(event) => {
    if (run.running) event.preventDefault();
  }}
/>

<main>
  <section aria-labelledby="page-title">
    <h1 id="page-title">Release a Deployment Version</h1>
    <form
      onsubmit={(event) => {
        event.preventDefault();
        submit();
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
      {#if !dryRun && !canRunLive}
        <p class="hint">
          Run a dry run with this version first. The live button is enabled once it finishes without
          errors.
        </p>
      {/if}
      <button
        type="submit"
        class:danger={!dryRun}
        disabled={run.running || !versionName || (!dryRun && !canRunLive)}
        >{run.running
          ? 'Releasing...'
          : dryRun
            ? 'Release Version'
            : 'Release Version (Live)'}</button
      >
    </form>
    {#if loadError}
      <p class="error" role="alert">{loadError}</p>
    {/if}
    {#if run.error}
      <p class="error" role="alert">{run.error}</p>
    {/if}
    {#if run.status !== 'idle'}
      <ScriptLog id="release-log" {run} {stale} filename="release-a-deployment-version" />
    {/if}
    {#if run.status === 'done' && run.dryRun && run.succeeded && !stale}
      <div class="apply-callout">
        <p>
          <strong>Dry run finished with no errors.</strong>
          Nothing has changed in Jira yet. Review the log, then apply the release.
        </p>
        <button type="button" class="danger" onclick={applyDryRun}>Apply These Changes</button>
      </div>
    {/if}
  </section>
</main>

<ConfirmDialog
  bind:open={confirmOpen}
  title={`Release ${versionName} in Jira?`}
  message="This releases the version and updates the issues that carry it: their Release State, comments on parent issues that are blocked, and publishing parent issues that are ready. Review the dry run log before you continue. This cannot be undone from here."
  confirmLabel="Release Version (Live)"
  onconfirm={() => void execute(false)}
  oncancel={cancelConfirm}
/>
