<script lang="ts">
  import { onMount } from 'svelte';
  import { getMessage } from '$lib/message';

  let message = $state('');
  let error = $state('');

  onMount(() => {
    void loadMessage();
  });

  async function loadMessage() {
    error = '';
    try {
      message = await getMessage();
    } catch {
      error = 'Unable to load the message from the backend.';
    }
  }
</script>

<svelte:head>
  <title>Svelte FastAPI Starter</title>
  <meta name="description" content="A minimal Svelte frontend and FastAPI backend." />
</svelte:head>

<main>
  <section aria-labelledby="page-title">
    <p class="eyebrow">Svelte + FastAPI</p>
    <h1 id="page-title">Starter application</h1>
    {#if error}
      <p class="error" role="alert">{error}</p>
    {:else if message}
      <p class="message" aria-live="polite">{message}</p>
    {:else}
      <p aria-live="polite">Loading message...</p>
    {/if}
  </section>
</main>
