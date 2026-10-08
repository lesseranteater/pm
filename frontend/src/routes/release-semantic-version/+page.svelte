<script lang="ts">
  import { releaseSemanticVersion } from '$lib/release-semantic-version';

  let versionName = $state('Hotfix.ps-dev-1.26.4.3');
  let dryRun = $state(false);
  let log = $state('');
  let error = $state('');
  let pending = $state(false);

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
    <p class="eyebrow">Jira release workflow</p>
    <h1 id="page-title">Release a semantic version</h1>
    <form
      onsubmit={(event) => {
        event.preventDefault();
        void releaseVersion();
      }}
    >
      <label for="deployment-version">Deployment Version</label>
      <input id="deployment-version" bind:value={versionName} maxlength="120" required />
      <fieldset>
        <legend>Dry Run</legend>
        <label><input type="radio" bind:group={dryRun} value={true} /> Yes</label>
        <label><input type="radio" bind:group={dryRun} value={false} /> No</label>
      </fieldset>
      <button type="submit" disabled={pending}>{pending ? 'Releasing...' : 'Release version'}</button>
    </form>
    {#if error}
      <p class="error" role="alert">{error}</p>
    {/if}
    {#if log}
      <label for="release-log">Release log</label>
      <textarea id="release-log" readonly value={log} rows="16"></textarea>
    {/if}
  </section>
</main>
