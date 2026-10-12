<script lang="ts">
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import { page } from '$app/state';
  import { tools, type ToolRoute } from '$lib/tools';
  import { onMount } from 'svelte';
  import JiraTokenDialog from '$lib/JiraTokenDialog.svelte';
  import ThemeSwitch from '$lib/ThemeSwitch.svelte';
  import UserMenu from '$lib/UserMenu.svelte';
  import '../app.css';

  // Follows the URL, so the back and forward buttons keep the dropdown in sync.
  // It is empty on the home page, where no tool is open yet.
  const selectedScript = $derived<ToolRoute | ''>(
    tools.find((tool) => tool.route === page.url.pathname)?.route ?? ''
  );
  let { children } = $props();
  let authStatus = $state<'checking' | 'signed-out' | 'signed-in'>('checking');
  let username = $state('');
  let password = $state('');
  let signedInUsername = $state('');
  let authError = $state('');
  let pending = $state(false);
  let jiraConfigured = $state(false);

  function jiraTokenRequired() {
    jiraConfigured = false;
  }

  function sessionExpired() {
    authStatus = 'signed-out';
    signedInUsername = '';
    password = '';
    jiraConfigured = false;
    authError = 'Your session expired. Please sign in again.';
  }

  onMount(() => {
    window.addEventListener('auth-expired', sessionExpired);
    window.addEventListener('jira-token-required', jiraTokenRequired);
    void checkSession();
    return () => {
      window.removeEventListener('auth-expired', sessionExpired);
      window.removeEventListener('jira-token-required', jiraTokenRequired);
    };
  });

  async function checkSession() {
    try {
      const response = await fetch('/api/auth/me');
      if (response.status === 401) {
        authStatus = 'signed-out';
        return;
      }
      if (!response.ok) throw new Error('Unable to check your session.');
      const user = (await response.json()) as { username?: unknown; jira_configured?: unknown };
      if (typeof user.username !== 'string') throw new Error('Invalid session response.');
      if (typeof user.jira_configured !== 'boolean') throw new Error('Invalid session response.');
      signedInUsername = user.username;
      jiraConfigured = user.jira_configured;
      authStatus = 'signed-in';
    } catch {
      authError = 'Unable to reach the server. Please try signing in again.';
      authStatus = 'signed-out';
    }
  }

  async function signIn() {
    pending = true;
    authError = '';
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as { detail?: unknown };
        throw new Error(typeof body.detail === 'string' ? body.detail : 'Unable to sign in.');
      }
      password = '';
      jiraConfigured = false;
      await checkSession();
    } catch (failure) {
      authError = failure instanceof Error ? failure.message : 'Unable to sign in.';
    } finally {
      pending = false;
    }
  }

  async function signOut() {
    pending = true;
    authError = '';
    try {
      const response = await fetch('/api/auth/logout', { method: 'POST' });
      if (!response.ok) throw new Error();
      authStatus = 'signed-out';
      signedInUsername = '';
      password = '';
      jiraConfigured = false;
    } catch {
      authError = 'Unable to sign out. Please try again.';
    } finally {
      pending = false;
    }
  }

  // Choosing a tool loads it straight away.
  function loadSelectedScript(event: Event & { currentTarget: HTMLSelectElement }) {
    void goto(resolve(event.currentTarget.value as ToolRoute));
  }
</script>

<header class="app-header">
  <div class="app-header-inner">
    <a class="brand" href={resolve('/')}>Release Management Tools</a>
    {#if authStatus === 'signed-in'}
      <div class="header-controls">
        <UserMenu username={signedInUsername} {pending} onsignout={signOut} />
        <div class="script-selector">
          <label for="script">Select a Tool</label>
          <select
            id="script"
            value={selectedScript}
            onchange={loadSelectedScript}
            disabled={!jiraConfigured}
          >
            {#if !selectedScript}
              <option value="" disabled></option>
            {/if}
            {#each tools as tool (tool.route)}
              <option value={tool.route}>{tool.title}</option>
            {/each}
          </select>
        </div>
      </div>
    {/if}
  </div>
</header>
<div class="app-shell">
  {#if authStatus === 'checking'}
    <p role="status">Checking your session...</p>
  {:else if authStatus === 'signed-out'}
    <main>
      <section aria-labelledby="login-title">
        <div class="login-theme"><ThemeSwitch /></div>
        <h1 id="login-title">Sign in</h1>
        <p class="intro">Sign in to access Release Management Tools.</p>
        <form
          onsubmit={(event) => {
            event.preventDefault();
            void signIn();
          }}
        >
          <label for="login-username">Email</label>
          <input
            id="login-username"
            type="email"
            autocomplete="username"
            bind:value={username}
            maxlength="254"
            required
          />
          <label for="login-password">Password</label>
          <input
            id="login-password"
            type="password"
            autocomplete="current-password"
            bind:value={password}
            maxlength="256"
            required
          />
          <button type="submit" disabled={pending}>{pending ? 'Signing in...' : 'Sign in'}</button>
        </form>
        {#if authError}<p class="error" role="alert">{authError}</p>{/if}
      </section>
    </main>
  {:else}
    {#if authError}<p class="error" role="alert">{authError}</p>{/if}
    {#if jiraConfigured}
      {@render children()}
    {:else}
      <JiraTokenDialog onsaved={() => (jiraConfigured = true)} onsignout={signOut} />
    {/if}
  {/if}
</div>
