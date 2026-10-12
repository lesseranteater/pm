<script lang="ts">
  import { onMount } from 'svelte';

  let dark = $state(false);

  function applyTheme() {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  }

  onMount(() => {
    let preference: string | null = null;
    try {
      preference = localStorage.getItem('pm-theme');
    } catch {
      // The switch still works when browser storage is unavailable.
    }
    dark =
      preference === 'dark' ||
      (preference !== 'light' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    applyTheme();
  });

  function toggle() {
    dark = !dark;
    applyTheme();
    try {
      localStorage.setItem('pm-theme', dark ? 'dark' : 'light');
    } catch {
      // Keep the chosen theme for this page even if it cannot be saved.
    }
  }
</script>

<button type="button" class="theme-switch" role="switch" aria-checked={dark} onclick={toggle}>
  <span class="theme-switch-track" aria-hidden="true"></span>
  Dark theme
</button>
