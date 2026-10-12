<script lang="ts">
  import ThemeSwitch from '$lib/ThemeSwitch.svelte';

  let {
    username,
    pending,
    onsignout
  }: {
    username: string;
    pending: boolean;
    onsignout: () => Promise<void>;
  } = $props();

  let open = $state(false);
  let root: HTMLDivElement | undefined = $state();
  let trigger: HTMLButtonElement | undefined = $state();

  function dismissOutside(event: Event) {
    if (open && event.target instanceof Node && !root?.contains(event.target)) open = false;
  }

  function closeWithEscape(event: KeyboardEvent) {
    if (!open || event.key !== 'Escape') return;
    event.preventDefault();
    open = false;
    trigger?.focus();
  }
</script>

<svelte:window
  onpointerdown={dismissOutside}
  onfocusin={dismissOutside}
  onkeydown={closeWithEscape}
/>

<div class="user-menu" bind:this={root}>
  <button
    type="button"
    class="user-menu-trigger"
    bind:this={trigger}
    aria-expanded={open}
    aria-controls="user-menu-panel"
    onclick={() => (open = !open)}
  >
    <span>{username}</span>
    <span aria-hidden="true">▾</span>
  </button>
  <div
    id="user-menu-panel"
    class="user-menu-panel"
    hidden={!open}
    role="region"
    aria-label="Account settings"
  >
    <p class="user-menu-identity">{username}</p>
    <div class="user-menu-preference"><ThemeSwitch /></div>
    <button
      type="button"
      class="user-menu-signout"
      disabled={pending}
      onclick={() => {
        open = false;
        void onsignout();
      }}>Sign out</button
    >
  </div>
</div>
