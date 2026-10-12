<script lang="ts">
  import { onDestroy, tick } from 'svelte';
  import { toFileStamp } from '$lib/dates';
  import type { ScriptRun } from '$lib/run.svelte';
  import { countLevels, filterLines, parseLogLines, plural } from '$lib/script-log';

  type Props = {
    id: string;
    run: ScriptRun;
    /** Base name for the downloaded file. */
    filename: string;
    /** A one-line, tool-specific result such as "36 versions: 15 Semantic, 21 Service." */
    summary?: string;
    /** The inputs have changed since this run, so the log may no longer match the form. */
    stale?: boolean;
  };

  let { id, run, filename, summary = '', stale = false }: Props = $props();

  let search = $state('');
  let problemsOnly = $state(false);
  let copyState = $state<'idle' | 'copied' | 'failed'>('idle');
  let resetTimer: ReturnType<typeof setTimeout> | undefined;
  let root: HTMLDivElement | undefined = $state();
  let output: HTMLPreElement | undefined = $state();
  let now = $state(Date.now());
  let followOutput = true;

  const counts = $derived(countLevels(run.log));
  const allLines = $derived(parseLogLines(run.log));
  const lines = $derived(filterLines(allLines, { search, problemsOnly }));
  const filtering = $derived(search.trim() !== '' || problemsOnly);

  const elapsedSeconds = $derived(
    (Math.max((run.running ? now : run.finishedAt) - run.startedAt, 0) / 1000).toFixed(1)
  );
  const statusText = $derived(
    run.status === 'running'
      ? `Running, ${elapsedSeconds} s`
      : run.status === 'failed'
        ? `Stopped after ${elapsedSeconds} s`
        : `Finished in ${elapsedSeconds} s`
  );
  // Read out only when the run starts or ends, not on every tick of the timer.
  const announcement = $derived(
    run.status === 'running'
      ? 'Running.'
      : run.status === 'failed'
        ? `The run stopped. ${run.error}`
        : `Finished. ${plural(counts.warnings, 'warning')}, ${plural(counts.errors, 'error')}.`
  );

  $effect(() => {
    if (!run.running) return;
    now = Date.now();
    const timer = setInterval(() => (now = Date.now()), 250);
    return () => clearInterval(timer);
  });

  // Bring the log into view whenever a run starts.
  $effect(() => {
    void run.startedAt;
    if (!root) return;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    root.scrollIntoView({ block: 'start', behavior: reduceMotion ? 'auto' : 'smooth' });
    followOutput = true;
  });

  // Follow new output while it streams in, unless the reader has scrolled up.
  $effect(() => {
    void run.log;
    if (!run.running || !followOutput) return;
    void tick().then(() => {
      if (output) output.scrollTop = output.scrollHeight;
    });
  });

  function noteScroll() {
    if (!output) return;
    followOutput = output.scrollTop + output.clientHeight >= output.scrollHeight - 24;
  }

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
    const text = run.log.trimEnd();
    try {
      await navigator.clipboard.writeText(text);
      copyState = 'copied';
    } catch {
      copyState = copyWithSelection(text) ? 'copied' : 'failed';
    }
    clearTimeout(resetTimer);
    resetTimer = setTimeout(() => (copyState = 'idle'), 2000);
  }

  function downloadLog() {
    const url = URL.createObjectURL(new Blob([run.log], { type: 'text/plain;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `${filename}-${toFileStamp(new Date(run.startedAt || Date.now()))}.txt`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  onDestroy(() => clearTimeout(resetTimer));
</script>

<div class="log" bind:this={root}>
  <div class="log-header">
    <p id="{id}-label" class="log-label">Script Log</p>
    <div class="log-actions">
      <button type="button" class="button-secondary" aria-live="polite" onclick={copyLog}>
        {copyState === 'copied' ? 'Copied' : copyState === 'failed' ? 'Copy Failed' : 'Copy Log'}
      </button>
      <button type="button" class="button-secondary" onclick={downloadLog} disabled={!run.log}>
        Download
      </button>
    </div>
  </div>

  {#if run.description}
    <p class="log-meta">{run.description}</p>
  {/if}

  <p class="log-status" aria-hidden="true">
    {#if run.running}<span class="spinner"></span>{/if}
    {statusText}
  </p>
  <p class="visually-hidden" role="status">{announcement}</p>

  {#if stale}
    <p class="notice">
      The inputs have changed since this run, so this log may not match the form. Run it again to
      refresh it.
    </p>
  {/if}

  {#if run.log}
    <p class="log-summary">
      {#if summary}<strong>{summary}</strong>{/if}
      <span>{plural(counts.entries, 'log entry', 'log entries')}</span>
      <span class:log-count-problem={counts.warnings > 0}>
        {plural(counts.warnings, 'warning')}
      </span>
      <span class:log-count-problem={counts.errors > 0}>{plural(counts.errors, 'error')}</span>
    </p>

    <div class="log-toolbar">
      <input
        type="search"
        class="log-search"
        placeholder="Search the log"
        aria-label="Search the log"
        bind:value={search}
      />
      <label class="log-filter">
        <input type="checkbox" bind:checked={problemsOnly} />
        Warnings and errors only
      </label>
      {#if filtering}
        <span class="log-filter-count" aria-live="polite">
          Showing {lines.length} of {allLines.length} lines
        </span>
      {/if}
    </div>

    <pre
      {id}
      bind:this={output}
      onscroll={noteScroll}
      class="release-log"
      class:stale
      role="log"
      aria-live="off"
      aria-labelledby="{id}-label">{#each lines as line, index (index)}<span
          class={line.level === 'WARNING' ? 'log-warning' : undefined}
          >{line.text}
</span>{/each}</pre>
  {:else if run.running}
    <p class="log-waiting">Waiting for the first line of output.</p>
  {/if}
</div>
