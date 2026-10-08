<script lang="ts">
  import { resolve } from '$app/paths';
  import { page } from '$app/state';
  import '../app.css';

  type ScriptRoute = '/service-versions' | '/release-semantic-version';

  const releaseRoute: ScriptRoute = '/release-semantic-version';
  let selectedScript = $state<ScriptRoute>(page.url.pathname === releaseRoute ? releaseRoute : '/service-versions');
  let { children } = $props();

  function executeSelectedScript() {
    const scriptSelector = document.getElementById('script') as HTMLSelectElement;
    window.location.assign(resolve(scriptSelector.value as ScriptRoute));
  }

</script>

<div class="app-shell">
  <header class="app-header">
    <a class="brand" href={resolve('/service-versions')}>Release Tools</a>
    <div class="script-selector">
      <label for="script">Script</label>
      <select id="script" bind:value={selectedScript}>
        <option value="/service-versions">Service Versions Without a Release Date</option>
        <option value={releaseRoute}>Release a Semantic Version</option>
      </select>
      <button type="button" onclick={executeSelectedScript}>Load</button>
    </div>
  </header>
  {@render children()}
</div>
