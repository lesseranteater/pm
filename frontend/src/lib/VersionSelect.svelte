<script lang="ts">
  import { tick } from 'svelte';
  import { fuzzyFilter, highlightSegments } from '$lib/fuzzy';

  type Props = {
    id: string;
    options: string[];
    value?: string;
    disabled?: boolean;
    placeholder?: string;
  };

  let { id, options, value = $bindable(''), disabled = false, placeholder = '' }: Props = $props();

  let open = $state(false);
  let query = $state('');
  let typing = $state(false);
  let activeIndex = $state(-1);
  let root: HTMLDivElement | undefined;
  let input: HTMLInputElement | undefined;
  let list: HTMLDivElement | undefined = $state();

  // The field shows the selected version until the user starts typing a search.
  const results = $derived(fuzzyFilter(options, typing ? query : ''));
  const inputText = $derived(typing ? query : value);
  const status = $derived(
    !open
      ? ''
      : results.length === 0
        ? 'No matching versions'
        : `${results.length} ${results.length === 1 ? 'version' : 'versions'} available`
  );

  async function openList() {
    if (disabled || options.length === 0 || open) return;
    open = true;
    activeIndex = Math.max(
      results.findIndex((result) => result.item === value),
      0
    );
    await tick();
    scrollActiveIntoView();
  }

  function closeList() {
    open = false;
    typing = false;
    query = '';
  }

  function choose(name: string) {
    value = name;
    closeList();
  }

  function scrollActiveIntoView() {
    list?.children[activeIndex]?.scrollIntoView({ block: 'nearest' });
  }

  function moveActive(next: number) {
    if (results.length === 0) return;
    activeIndex = Math.min(Math.max(next, 0), results.length - 1);
    void tick().then(scrollActiveIntoView);
  }

  function onInput(event: Event & { currentTarget: HTMLInputElement }) {
    query = event.currentTarget.value;
    typing = true;
    open = true;
    activeIndex = 0;
    void tick().then(() => list && (list.scrollTop = 0));
  }

  function onFocus() {
    void openList();
    // Selecting the text means the first keystroke replaces it with a search.
    requestAnimationFrame(() => input?.select());
  }

  function onKeydown(event: KeyboardEvent) {
    if (disabled) return;
    switch (event.key) {
      case 'ArrowDown':
      case 'ArrowUp':
        event.preventDefault();
        if (!open) void openList();
        else moveActive(activeIndex + (event.key === 'ArrowDown' ? 1 : -1));
        break;
      case 'Home':
      case 'End':
        if (!open || !typing) return; // let the caret move when not searching
        event.preventDefault();
        moveActive(event.key === 'Home' ? 0 : results.length - 1);
        break;
      case 'Enter':
        event.preventDefault();
        if (open && results[activeIndex]) choose(results[activeIndex].item);
        break;
      case 'Escape':
        if (open) {
          event.preventDefault();
          closeList();
        }
        break;
      case 'Tab':
        closeList();
        break;
    }
  }

  function onWindowPointerDown(event: PointerEvent) {
    if (open && root && !root.contains(event.target as Node)) closeList();
  }
</script>

<svelte:window onpointerdown={onWindowPointerDown} />

<div class="version-select" bind:this={root}>
  <input
    {id}
    bind:this={input}
    class="version-select-input"
    type="text"
    role="combobox"
    autocomplete="off"
    spellcheck="false"
    aria-autocomplete="list"
    aria-expanded={open}
    aria-controls="{id}-listbox"
    aria-activedescendant={open && results[activeIndex] ? `${id}-option-${activeIndex}` : undefined}
    {placeholder}
    {disabled}
    value={inputText}
    oninput={onInput}
    onfocus={onFocus}
    onclick={() => {
      void openList();
      if (!typing) input?.select();
    }}
    onkeydown={onKeydown}
  />
  <p class="visually-hidden" role="status">{status}</p>
  {#if open}
    <div
      id="{id}-listbox"
      class="version-select-list"
      role="listbox"
      tabindex="-1"
      bind:this={list}
      onpointerdown={(event) => event.preventDefault()}
    >
      {#each results as result, index (result.item)}
        <div
          id="{id}-option-{index}"
          class="version-select-option"
          class:active={index === activeIndex}
          role="option"
          tabindex="-1"
          aria-selected={result.item === value}
          onpointermove={() => (activeIndex = index)}
          onkeydown={onKeydown}
          onclick={() => choose(result.item)}
        >
          {#each highlightSegments(result.item, result.indices) as segment, position (position)}{#if segment.match}<mark
                >{segment.text}</mark
              >{:else}{segment.text}{/if}{/each}
        </div>
      {:else}
        <div class="version-select-empty">No matching versions</div>
      {/each}
    </div>
  {/if}
</div>
