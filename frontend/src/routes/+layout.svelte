<script lang="ts">
  import { resolve } from '$app/paths';
  import { page } from '$app/state';
  import '../app.css';

  const scripts = [
    { route: '/service-versions', title: 'Service Versions Without a Release Date' },
    { route: '/release-semantic-version', title: 'Release a Semantic Version' },
    { route: '/archive-released-versions', title: 'Archive Released Versions' }
  ] as const;

  type ScriptRoute = (typeof scripts)[number]['route'];

  let selectedScript = $state<ScriptRoute>(
    scripts.find((script) => script.route === page.url.pathname)?.route ?? '/service-versions'
  );
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
      <select id="script" aria-label="Script" bind:value={selectedScript}>
        {#each scripts as script (script.route)}
          <option value={script.route}>{script.title}</option>
        {/each}
      </select>
      <button type="button" onclick={executeSelectedScript}>Load</button>
    </div>
  </header>
  {@render children()}
</div>
