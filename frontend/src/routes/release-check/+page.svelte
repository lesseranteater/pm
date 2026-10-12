<script lang="ts">
  import ScriptLog from '$lib/ScriptLog.svelte';
  import { runReleaseCheck } from '$lib/release-check';
  import { ScriptRun } from '$lib/run.svelte';

  const DEPLOYMENT_PLAN_KEY_PATTERN = /^[A-Z][A-Z0-9_]{1,9}-\d+$/;
  const run = new ScriptRun();

  let deploymentPlanKey = $state('');
  let formError = $state('');

  const normalizedKey = $derived(deploymentPlanKey.trim().toUpperCase());
  const stale = $derived(run.status !== 'idle' && run.signature !== normalizedKey);

  async function runCheck() {
    formError = '';
    if (!DEPLOYMENT_PLAN_KEY_PATTERN.test(normalizedKey)) {
      formError = 'Enter a valid Deployment Plan Key, for example IGM-123.';
      return;
    }

    deploymentPlanKey = normalizedKey;
    await run.start(
      { description: `Deployment Plan ${normalizedKey}`, signature: normalizedKey, dryRun: false },
      (onText) => runReleaseCheck(normalizedKey, onText)
    );
  }
</script>

<svelte:head>
  <title>Release Check</title>
  <meta name="description" content="Check a Deployment Plan for Jira Fix Version mismatches." />
</svelte:head>

<svelte:window
  onbeforeunload={(event) => {
    if (run.running) event.preventDefault();
  }}
/>

<main>
  <section aria-labelledby="page-title">
    <h1 id="page-title">Release Check</h1>
    <p class="intro">
      Checks the linked issues, their parents and direct sub-tasks for Fix Version mismatches. It
      only reads from Jira, so nothing is changed.
    </p>
    <form
      onsubmit={(event) => {
        event.preventDefault();
        void runCheck();
      }}
    >
      <label for="deployment-plan-key">Deployment Plan Key</label>
      <input id="deployment-plan-key" bind:value={deploymentPlanKey} maxlength="20" required />
      <button type="submit" disabled={run.running}>{run.running ? 'Checking...' : 'Run Check'}</button>
    </form>
    {#if formError}
      <p class="error" role="alert">{formError}</p>
    {/if}
    {#if run.error}
      <p class="error" role="alert">{run.error}</p>
    {/if}
    {#if run.status !== 'idle'}
      <ScriptLog id="release-check-log" {run} {stale} filename="release-check" />
    {/if}
  </section>
</main>
