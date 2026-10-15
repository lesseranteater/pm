<script lang="ts">
  import {
    archiveReleasedVersions,
    getArchivePreview,
    parseVersionNames,
    type ArchivePreview
  } from '$lib/archive-released-versions';
  import ConfirmDialog from '$lib/ConfirmDialog.svelte';
  import { addDays, formatDateInputValue, toDateInputValue } from '$lib/dates';
  import { foundVersionCount, summarizeArchive } from '$lib/log-summaries';
  import { ScriptRun } from '$lib/run.svelte';
  import ScriptLog from '$lib/ScriptLog.svelte';
  import { plural } from '$lib/script-log';
  import { ApiError } from '$lib/stream';

  const PROJECT_KEY_PATTERN = /^[A-Z][A-Z0-9_]{1,9}$/;

  const now = new Date();
  const today = toDateInputValue(now);

  const run = new ScriptRun();

  let projectKey = $state('IGM');
  // Defaults to yesterday, so a run archives versions released before today.
  let archiveUntil = $state(toDateInputValue(addDays(now, -1)));
  let archiveBy = $state<'date' | 'versions'>('date');
  let versionList = $state('');
  let dryRun = $state(true);
  let formError = $state('');
  // The inputs of the last dry run that finished without errors. A live run needs a match.
  let verifiedSignature = $state('');
  let confirmOpen = $state(false);
  let openedFromShortcut = false;

  let preview = $state<ArchivePreview | null>(null);
  let previewState = $state<'idle' | 'loading' | 'ready' | 'error'>('idle');
  let previewError = $state('');
  let previewRequest = 0;

  const normalizedKey = $derived(projectKey.trim().toUpperCase());
  const dateText = $derived(formatDateInputValue(archiveUntil));
  const versionNames = $derived(parseVersionNames(versionList));
  const selection = $derived(archiveBy === 'date' ? archiveUntil : versionNames);
  const inputsValid = $derived(
    PROJECT_KEY_PATTERN.test(normalizedKey) &&
      (archiveBy === 'date'
        ? dateText !== '' && archiveUntil <= today
        : versionNames.length > 0 &&
          versionNames.length <= 500 &&
          versionNames.every((name) => name.length <= 255))
  );
  const signature = $derived(JSON.stringify([normalizedKey, archiveBy, selection]));
  const listPreviewValid = $derived(
    archiveBy === 'date' ||
      (previewState === 'ready' && preview !== null && preview.unknown?.length === 0)
  );
  const canRunLive = $derived(verifiedSignature === signature);
  const stale = $derived(run.status !== 'idle' && run.signature !== signature);
  const dryRunFound = $derived(run.dryRun ? foundVersionCount(run.log) : null);
  const confirmCount = $derived(dryRunFound ?? preview?.count ?? null);

  // Count the matching versions as the project or date changes. This only reads from Jira.
  $effect(() => {
    const key = normalizedKey;
    const until = selection;
    if (!inputsValid) {
      preview = null;
      previewState = 'idle';
      return;
    }

    const request = ++previewRequest;
    previewState = 'loading';
    const timer = setTimeout(async () => {
      try {
        const result = await getArchivePreview(key, until);
        if (request !== previewRequest) return;
        preview = result;
        previewState = 'ready';
      } catch (failure) {
        if (request !== previewRequest) return;
        preview = null;
        previewError =
          failure instanceof ApiError && failure.detail
            ? failure.detail
            : 'The preview is unavailable.';
        previewState = 'error';
      }
    }, 400);

    return () => {
      clearTimeout(timer);
      previewRequest++;
    };
  });

  async function execute(isDryRun: boolean) {
    formError = '';
    if (!PROJECT_KEY_PATTERN.test(normalizedKey)) {
      formError = 'Enter a valid project key, for example IGM.';
      return;
    }
    if (!inputsValid || !listPreviewValid) {
      formError =
        archiveBy === 'date'
          ? 'Choose a date that is not in the future.'
          : 'Enter valid version names and resolve unknown names before running.';
      return;
    }

    const key = normalizedKey;
    const until = selection;
    const runSignature = signature;
    projectKey = key;
    verifiedSignature = '';

    await run.start(
      {
        description: `${isDryRun ? 'Dry run' : 'Live run'}, ${key}, ${archiveBy === 'date' ? `up to ${dateText}` : `versions: ${versionNames.join(', ')}`}`,
        signature: runSignature,
        dryRun: isDryRun
      },
      (onText) => archiveReleasedVersions(key, until, isDryRun, onText)
    );

    // Only a dry run that finished cleanly unlocks the live run for these same inputs.
    verifiedSignature = isDryRun && run.succeeded ? runSignature : '';
  }

  function submit() {
    if (run.running) return;
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
  <title>Archive Released Versions</title>
  <meta
    name="description"
    content="Archive Jira versions that were released up to a date you choose."
  />
</svelte:head>

<svelte:window
  onbeforeunload={(event) => {
    if (run.running) event.preventDefault();
  }}
/>

<main>
  <section aria-labelledby="page-title">
    <h1 id="page-title">Archive Released Versions</h1>
    <p class="intro">
      Archive released versions by release date or by exact version names. Nothing runs until you
      click Archive Versions.
    </p>
    <form
      onsubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <label for="archive-project-key">Project Key</label>
      <input
        id="archive-project-key"
        bind:value={projectKey}
        oninput={() => (verifiedSignature = '')}
        maxlength="10"
        required
      />
      <fieldset>
        <legend>Archive By</legend>
        <label
          ><input
            type="radio"
            name="archive-method"
            bind:group={archiveBy}
            value="date"
            onchange={() => (verifiedSignature = '')}
          /> Release date</label
        >
        <label
          ><input
            type="radio"
            name="archive-method"
            bind:group={archiveBy}
            value="versions"
            onchange={() => (verifiedSignature = '')}
          /> Version list</label
        >
      </fieldset>
      {#if archiveBy === 'date'}
        <label for="archive-until">Archive Versions Released Up To</label>
        <input
          id="archive-until"
          type="date"
          bind:value={archiveUntil}
          oninput={() => (verifiedSignature = '')}
          max={today}
          required
        />
      {:else}
        <label for="archive-version-names">Version Names</label>
        <textarea
          id="archive-version-names"
          class="version-names"
          bind:value={versionList}
          oninput={() => (verifiedSignature = '')}
          rows="4"
          maxlength="20000"
          aria-describedby="version-names-help"
          required></textarea>
        <p id="version-names-help" class="intro">
          Enter exact Jira version names, separated by commas. Whitespace and duplicates are
          ignored. Release dates are not used in this mode.
        </p>
      {/if}
      <p class="preview" class:preview-error={previewState === 'error'} aria-live="polite">
        {#if previewState === 'loading'}
          Checking how many versions match...
        {:else if previewState === 'ready' && preview}
          {#if preview.count === 0}
            {archiveBy === 'date'
              ? `No released versions on or before ${dateText} would be archived.`
              : 'No eligible released versions in the list would be archived.'}
          {:else}
            <strong>{plural(preview.count, 'version')}</strong> would be archived ({preview.semantic}
            Semantic, {preview.service} Service).
          {/if}
        {:else if previewState === 'error'}
          {previewError}
        {/if}
      </p>
      {#if archiveBy === 'versions' && previewState === 'ready' && preview}
        <div class="version-list-preview" aria-label="Version list preview">
          {#if preview.eligible?.length}<p>
              <strong>Eligible:</strong>
              {preview.eligible.join(', ')}
            </p>{/if}
          {#if preview.unknown?.length}<p class="error" role="alert">
              <strong>Unknown names:</strong>
              {preview.unknown.join(', ')}. Correct these names before running.
            </p>{/if}
          {#if preview.unreleased?.length}<p>
              <strong>Skipped — unreleased:</strong>
              {preview.unreleased.join(', ')}
            </p>{/if}
          {#if preview.already_archived?.length}<p>
              <strong>Skipped — already archived:</strong>
              {preview.already_archived.join(', ')}
            </p>{/if}
        </div>
      {/if}
      <fieldset>
        <legend>Dry Run</legend>
        <label><input type="radio" bind:group={dryRun} value={true} /> Yes</label>
        <label><input type="radio" bind:group={dryRun} value={false} /> No</label>
      </fieldset>
      <p class="notice" class:notice-warning={!dryRun} role="note">
        {#if archiveBy === 'versions'}
          Only released, unarchived versions named in your list in {normalizedKey || 'the project'} will
          be archived. Release dates are ignored.
        {:else if dateText}
          All released versions in {normalizedKey || 'the project'} with a release date on or before
          <strong>{dateText}</strong> will be archived.
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
      {#if !dryRun && !canRunLive}
        <p class="hint">
          Run a dry run with these settings first. The live button is enabled once it finishes
          without errors.
        </p>
      {/if}
      <button
        type="submit"
        class:danger={!dryRun}
        disabled={run.running || !inputsValid || !listPreviewValid || (!dryRun && !canRunLive)}
        >{run.running
          ? 'Archiving...'
          : dryRun
            ? 'Archive Versions'
            : 'Archive Versions (Live)'}</button
      >
    </form>
    {#if formError}
      <p class="error" role="alert">{formError}</p>
    {/if}
    {#if run.error}
      <p class="error" role="alert">{run.error}</p>
    {/if}
    {#if run.status !== 'idle'}
      <ScriptLog
        id="archive-log"
        {run}
        {stale}
        filename="archive-released-versions"
        summary={summarizeArchive(run.log)}
      />
    {/if}
    {#if run.status === 'done' && run.dryRun && run.succeeded && !stale && dryRunFound && listPreviewValid && canRunLive}
      <div class="apply-callout">
        <p>
          <strong>Dry run finished with no errors.</strong>
          {plural(dryRunFound, 'version')} would be archived. Nothing has changed in Jira yet.
        </p>
        <button type="button" class="danger" onclick={applyDryRun}>Apply These Changes</button>
      </div>
    {/if}
  </section>
</main>

<ConfirmDialog
  bind:open={confirmOpen}
  title={confirmCount === null
    ? `Archive released versions in ${normalizedKey}?`
    : `Archive ${plural(confirmCount, 'version')} in ${normalizedKey}?`}
  message={`${archiveBy === 'date' ? `Every released version in ${normalizedKey} with a release date on or before ${dateText}` : `The released, unarchived versions in ${normalizedKey} named in your list (${versionNames.join(', ')})`} will be archived in Jira, Semantic versions first and then Service versions. Review the dry run log before you continue. This cannot be undone from here.`}
  confirmLabel="Archive Versions (Live)"
  onconfirm={() => void execute(false)}
  oncancel={cancelConfirm}
/>
