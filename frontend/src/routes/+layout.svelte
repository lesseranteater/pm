<script lang="ts">
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import { page } from '$app/state';
  import '../app.css';

  const scripts = [
    { route: '/service-versions', title: 'Service Versions Without a Release Date' },
    { route: '/release-semantic-version', title: 'Release a Semantic Version' },
    { route: '/archive-released-versions', title: 'Archive Released Versions' }
  ] as const;

  type ScriptRoute = (typeof scripts)[number]['route'];

  // Follows the URL, so the back and forward buttons keep the dropdown in sync.
  const selectedScript = $derived<ScriptRoute>(
    scripts.find((script) => script.route === page.url.pathname)?.route ?? '/service-versions'
  );
  let { children } = $props();

  // Choosing a tool loads it straight away.
  function loadSelectedScript(event: Event & { currentTarget: HTMLSelectElement }) {
    void goto(resolve(event.currentTarget.value as ScriptRoute));
  }
</script>

<header class="app-header">
  <div class="app-header-inner">
    <a class="brand" href={resolve('/service-versions')}>Release Tools</a>
    <div class="script-selector">
      <label for="script">Select a Tool</label>
      <select id="script" value={selectedScript} onchange={loadSelectedScript}>
        {#each scripts as script (script.route)}
          <option value={script.route}>{script.title}</option>
        {/each}
      </select>
    </div>
  </div>
</header>
<div class="app-shell">
  {@render children()}
</div>
