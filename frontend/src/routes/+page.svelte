<script lang="ts">
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import { onMount } from 'svelte';

  onMount(() => {
    void goto(resolve('/service-versions'), { replaceState: true });
  });
</script>

<svelte:head>
  <title>Release Tools</title>
  <meta http-equiv="refresh" content="0; url=/service-versions" />
</svelte:head>
