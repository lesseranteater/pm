<script lang="ts">
  import { tick } from 'svelte';

  type Props = {
    id: string;
    options: string[];
    value?: string;
    disabled?: boolean;
    placeholder?: string;
  };

  let { id, options, value = $bindable(''), disabled = false, placeholder = '' }: Props = $props();

  let open = $state(false);
  let activeIndex = $state(-1);
  let root: HTMLDivElement | undefined;
  let list: HTMLDivElement | undefined = $state();

  async function openList() {
    if (disabled || options.length === 0) return;
    open = true;
    activeIndex = Math.max(options.indexOf(value), 0);
    await tick();
    scrollActiveIntoView();
  }

  function closeList() {
    open = false;
  }

  function choose(name: string) {
    value = name;
    closeList();
  }

  function scrollActiveIntoView() {
    list?.children[activeIndex]?.scrollIntoView({ block: 'nearest' });
  }

  function moveActive(next: number) {
    activeIndex = Math.min(Math.max(next, 0), options.length - 1);
    void tick().then(scrollActiveIntoView);
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
        if (!open) return;
        event.preventDefault();
        moveActive(event.key === 'Home' ? 0 : options.length - 1);
        break;
      case 'Enter':
      case ' ':
        event.preventDefault();
        if (open && activeIndex >= 0) choose(options[activeIndex]);
        else void openList();
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
  <button
    {id}
    type="button"
    class="version-select-button"
    role="combobox"
    aria-haspopup="listbox"
    aria-expanded={open}
    aria-controls="{id}-listbox"
    aria-activedescendant={open && activeIndex >= 0 ? `${id}-option-${activeIndex}` : undefined}
    {disabled}
    onclick={() => (open ? closeList() : void openList())}
    onkeydown={onKeydown}
  >
    <span class="version-select-value">{value || placeholder}</span>
  </button>
  {#if open}
    <div
      id="{id}-listbox"
      class="version-select-list"
      role="listbox"
      tabindex="-1"
      bind:this={list}
      onpointerdown={(event) => event.preventDefault()}
    >
      {#each options as name, index (name)}
        <div
          id="{id}-option-{index}"
          class="version-select-option"
          class:active={index === activeIndex}
          role="option"
          tabindex="-1"
          aria-selected={name === value}
          onpointermove={() => (activeIndex = index)}
          onkeydown={onKeydown}
          onclick={() => choose(name)}
        >
          {name}
        </div>
      {/each}
    </div>
  {/if}
</div>
