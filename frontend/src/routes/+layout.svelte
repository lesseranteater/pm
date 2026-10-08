<script lang="ts">
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import { page } from '$app/state';
  import { tools, type ToolRoute } from '$lib/tools';
  import '../app.css';

  // Follows the URL, so the back and forward buttons keep the dropdown in sync.
  // It is empty on the home page, where no tool is open yet.
  const selectedScript = $derived<ToolRoute | ''>(
    tools.find((tool) => tool.route === page.url.pathname)?.route ?? ''
  );
  let { children } = $props();

  // Choosing a tool loads it straight away.
  function loadSelectedScript(event: Event & { currentTarget: HTMLSelectElement }) {
    void goto(resolve(event.currentTarget.value as ToolRoute));
  }
</script>

<header class="app-header">
  <div class="app-header-inner">
    <a class="brand" href={resolve('/')}>Release Management Tools</a>
    <div class="script-selector">
      <label for="script">Select a Tool</label>
      <select id="script" value={selectedScript} onchange={loadSelectedScript}>
        {#if !selectedScript}
          <option value="" disabled>Choose a tool</option>
        {/if}
        {#each tools as tool (tool.route)}
          <option value={tool.route}>{tool.title}</option>
        {/each}
      </select>
    </div>
  </div>
</header>
<div class="app-shell">
  {@render children()}
</div>
