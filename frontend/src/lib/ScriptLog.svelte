<script lang="ts">
  import { parseLogLines } from '$lib/script-log';

  let { id, log }: { id: string; log: string } = $props();
</script>

<p id="{id}-label" class="log-label">Script Log</p>
<pre
  {id}
  class="release-log"
  role="log"
  aria-labelledby="{id}-label">{#each parseLogLines(log) as line, index (index)}<span
      class={line.level === 'WARNING' ? 'log-warning' : undefined}
      >{line.text}
</span>{/each}</pre>
