<script lang="ts">
  let { onsaved, onsignout }: { onsaved: () => void; onsignout: () => Promise<void> } = $props();
  let dialog: HTMLDialogElement | undefined = $state();
  let input: HTMLInputElement | undefined = $state();
  let token = $state('');
  let error = $state('');
  let pending = $state(false);

  $effect(() => {
    if (dialog && !dialog.open) {
      dialog.showModal();
      input?.focus();
    }
  });

  async function saveToken() {
    if (pending) return;
    error = '';
    pending = true;
    try {
      const response = await fetch('/api/auth/jira-token', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ token: token.trim() })
      });
      if (response.status === 401) {
        window.dispatchEvent(new Event('auth-expired'));
        return;
      }
      if (!response.ok) throw new Error();
      token = '';
      dialog?.close();
      onsaved();
    } catch {
      error = 'Unable to save your Jira token. Please try again.';
    } finally {
      pending = false;
    }
  }

  async function signOut() {
    pending = true;
    await onsignout();
    pending = false;
  }
</script>

<dialog
  bind:this={dialog}
  class="confirm-dialog jira-token-dialog"
  aria-labelledby="jira-token-title"
  aria-describedby="jira-token-description"
  oncancel={(event) => event.preventDefault()}
>
  <h2 id="jira-token-title">Enter your Jira token</h2>
  <p id="jira-token-description">
    Enter your Jira Personal Access Token to use the tools. It is stored in an HTTP-only browser
    cookie and cleared when you sign out.
  </p>
  <form
    onsubmit={(event) => {
      event.preventDefault();
      void saveToken();
    }}
  >
    <label for="jira-token">Jira Token</label>
    <input
      id="jira-token"
      type="password"
      bind:this={input}
      bind:value={token}
      autocomplete="off"
      maxlength="2048"
      required
    />
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    <div class="confirm-actions">
      <button
        type="button"
        class="button-secondary"
        disabled={pending}
        onclick={() => void signOut()}>Sign out</button
      >
      <button type="submit" disabled={pending || !token.trim()}
        >{pending ? 'Saving...' : 'Save Token'}</button
      >
    </div>
  </form>
</dialog>
