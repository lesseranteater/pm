<script lang="ts">
  import { onDestroy } from 'svelte';
  import { parseLogLines } from '$lib/script-log';

  let { id, log }: { id: string; log: string } = $props();

  let copyState = $state<'idle' | 'copied' | 'failed'>('idle');
  let resetTimer: ReturnType<typeof setTimeout> | undefined;

  // Older selection-based copy, for browsers that deny the async clipboard API.
  function copyWithSelection(text: string): boolean {
    const field = document.createElement('textarea');
    field.value = text;
    field.setAttribute('readonly', '');
    field.style.position = 'fixed';
    field.style.opacity = '0';
    document.body.append(field);
    field.select();
    try {
      return document.execCommand('copy');
    } finally {
      field.remove();
    }
  }

  async function copyLog() {
    const text = log.trimEnd();
    try {
      await navigator.clipboard.writeText(text);
      copyState = 'copied';
    } catch {
      copyState = copyWithSelection(text) ? 'copied' : 'failed';
    }
    clearTimeout(resetTimer);
    resetTimer = setTimeout(() => (copyState = 'idle'), 2000);
  }

  onDestroy(() => clearTimeout(resetTimer));
</script>

<div class="log-header">
  <p id="{id}-label" class="log-label">Script Log</p>
  <button type="button" class="button-secondary" aria-live="polite" onclick={copyLog}>
    {copyState === 'copied' ? 'Copied' : copyState === 'failed' ? 'Copy Failed' : 'Copy Log'}
  </button>
</div>
<pre
  {id}
  class="release-log"
  role="log"
  aria-labelledby="{id}-label">{#each parseLogLines(log) as line, index (index)}<span
      class={line.level === 'WARNING' ? 'log-warning' : undefined}
      >{line.text}
</span>{/each}</pre>
