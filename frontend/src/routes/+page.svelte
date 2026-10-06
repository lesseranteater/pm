<script lang="ts">
  import { resolve } from '$app/paths';
  import { onMount } from 'svelte';
  import { type Card, type Column } from '$lib/board';
  import * as api from '$lib/api';

  type AuthStatus = 'checking' | 'signed-out' | 'signed-in';

  let authStatus = $state<AuthStatus>('checking');
  let signedInUsername = $state('');
  let loginUsername = $state('');
  let loginPassword = $state('');
  let loginError = $state('');
  let loginPending = $state(false);
  let columns = $state<Column[]>([]);
  let boardPending = $state(false);
  let savingAction = $state<string | null>(null);
  let boardError = $state('');
  let draggedCardId = $state<string | null>(null);
  let editingCardId = $state<string | null>(null);
  let editingColumnId = $state<string | null>(null);
  let newCardColumnId = $state<string | null>(null);
  let draftTitle = $state('');
  let draftDetails = $state('');
  let draftColumnName = $state('');
  let newTitle = $state('');
  let newDetails = $state('');
  let statusMessage = $state('');

  const cardCount = $derived(columns.reduce((total, column) => total + column.cards.length, 0));

  onMount(() => {
    void loadSession();
  });

  async function loadSession() {
    try {
      const response = await globalThis.fetch('/api/auth/me', { credentials: 'same-origin' });
      if (!response.ok) {
        authStatus = 'signed-out';
        return;
      }
      const user = (await response.json()) as { username: string };
      signedInUsername = user.username;
      if (await loadBoard()) authStatus = 'signed-in';
    } catch {
      loginError = 'Unable to reach the server. Try again shortly.';
      authStatus = 'signed-out';
    }
  }

  async function loadBoard(): Promise<boolean> {
    boardPending = true;
    boardError = '';
    try {
      columns = api.toColumns(await api.getBoard());
      return true;
    } catch (error) {
      handleApiError(error, 'Unable to load the board');
      return false;
    } finally {
      boardPending = false;
    }
  }

  async function submitLogin(event: globalThis.SubmitEvent) {
    event.preventDefault();
    loginPending = true;
    loginError = '';
    try {
      const response = await globalThis.fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ username: loginUsername, password: loginPassword })
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(body?.detail ?? 'Unable to sign in');
      }
      const user = (await response.json()) as { username: string };
      signedInUsername = user.username;
      loginPassword = '';
      columns = api.toColumns(await api.getBoard());
      authStatus = 'signed-in';
    } catch (error) {
      loginError = error instanceof Error ? error.message : 'Unable to sign in';
    } finally {
      loginPending = false;
    }
  }

  async function logout() {
    await globalThis
      .fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'same-origin'
      })
      .catch(() => undefined);
    columns = [];
    signedInUsername = '';
    authStatus = 'signed-out';
  }

  function findCard(cardId: string): { card: Card; column: Column } | null {
    for (const column of columns) {
      const card = column.cards.find((item) => item.id === cardId);
      if (card) return { card, column };
    }
    return null;
  }

  function startEditCard(cardId: string) {
    const result = findCard(cardId);
    if (!result) return;
    editingCardId = cardId;
    draftTitle = result.card.title;
    draftDetails = result.card.details;
  }

  async function saveCard(cardId: string) {
    const result = findCard(cardId);
    const title = draftTitle.trim();
    if (!result || !title) return;
    savingAction = `card:${cardId}`;
    try {
      columns = api.toColumns(await api.updateCard(cardId, title, draftDetails.trim()));
      editingCardId = null;
      statusMessage = `Updated ${title}`;
    } catch (error) {
      handleApiError(error, 'Unable to update card');
    } finally {
      savingAction = null;
    }
  }

  async function deleteCard(cardId: string) {
    const result = findCard(cardId);
    if (!result) return;
    savingAction = `delete:${cardId}`;
    try {
      columns = api.toColumns(await api.removeCard(cardId));
      if (editingCardId === cardId) editingCardId = null;
      statusMessage = `Deleted ${result.card.title}`;
    } catch (error) {
      handleApiError(error, 'Unable to delete card');
    } finally {
      savingAction = null;
    }
  }

  function startRename(column: Column) {
    editingColumnId = column.id;
    draftColumnName = column.name;
  }

  async function saveColumnName(column: Column) {
    const name = draftColumnName.trim();
    if (!name) return;
    savingAction = `column:${column.id}`;
    try {
      columns = api.toColumns(await api.renameColumn(column.id, name));
      editingColumnId = null;
      statusMessage = `Renamed column to ${name}`;
    } catch (error) {
      handleApiError(error, 'Unable to rename column');
    } finally {
      savingAction = null;
    }
  }

  function openNewCard(columnId: string) {
    newCardColumnId = columnId;
    newTitle = '';
    newDetails = '';
  }

  async function addCard(column: Column) {
    const title = newTitle.trim();
    if (!title) return;
    savingAction = `new:${column.id}`;
    try {
      columns = api.toColumns(await api.addCard(column.id, title, newDetails));
      newCardColumnId = null;
      statusMessage = `Added ${title} to ${column.name}`;
    } catch (error) {
      handleApiError(error, 'Unable to add card');
    } finally {
      savingAction = null;
    }
  }

  async function moveCard(cardId: string, destinationId: string) {
    const result = findCard(cardId);
    const destination = columns.find((column) => column.id === destinationId);
    if (!result || !destination || result.column.id === destinationId) return;
    savingAction = `move:${cardId}`;
    try {
      columns = api.toColumns(await api.moveCard(cardId, destinationId));
      statusMessage = `Moved ${result.card.title} to ${destination.name}`;
    } catch (error) {
      handleApiError(error, 'Unable to move card');
    } finally {
      savingAction = null;
    }
  }

  function handleApiError(error: unknown, fallback: string) {
    const message = error instanceof Error ? error.message : fallback;
    boardError = message;
    statusMessage = message;
    if (error instanceof api.ApiError && error.status === 401) {
      columns = [];
      signedInUsername = '';
      authStatus = 'signed-out';
      loginError = 'Your session expired. Please sign in again.';
    }
  }

  function handleDragStart(
    event: { dataTransfer: globalThis.DataTransfer | null },
    cardId: string
  ) {
    draggedCardId = cardId;
    event.dataTransfer?.setData('text/plain', cardId);
    if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
  }

  function handleDrop(
    event: { dataTransfer: globalThis.DataTransfer | null; preventDefault: () => void },
    columnId: string
  ) {
    event.preventDefault();
    const cardId = event.dataTransfer?.getData('text/plain') || draggedCardId;
    if (cardId) moveCard(cardId, columnId);
    draggedCardId = null;
  }

  function handleDragEnd() {
    draggedCardId = null;
  }
</script>

<svelte:head>
  <title>Northstar Board | Project management</title>
  <meta name="description" content="A focused, lightweight Kanban board for moving work forward." />
</svelte:head>

<div class="app-shell">
  <header class="topbar">
    <a class="brand" href={resolve('/')} aria-label="Northstar Board home">
      <span class="brand-mark" aria-hidden="true">N</span>
      <span>Northstar <strong>Board</strong></span>
    </a>
    <div class="topbar-meta">
      {#if authStatus === 'signed-in'}
        <span class="live-indicator"><span></span> Local workspace</span>
        <span class="signed-in-name">{signedInUsername}</span>
        <button class="logout-button" type="button" onclick={logout}>Log out</button>
      {:else if authStatus === 'checking'}
        <span class="live-indicator"><span></span> Checking session</span>
      {/if}
    </div>
  </header>

  {#if authStatus === 'checking'}
    <main class="auth-page" aria-live="polite">
      <div class="auth-card loading-card">
        <span class="auth-kicker">Northstar Board</span>
        <h1>Checking your workspace.</h1>
        <p>One moment while we restore your session.</p>
      </div>
    </main>
  {:else if authStatus === 'signed-out'}
    <main class="auth-page">
      <section class="auth-card" aria-labelledby="login-title">
        <span class="auth-kicker">Private workspace</span>
        <h1 id="login-title">Welcome back.</h1>
        <p>Sign in to continue to your project board.</p>
        <form class="login-form" onsubmit={submitLogin}>
          <label for="login-username">Username</label>
          <input id="login-username" bind:value={loginUsername} autocomplete="username" required />
          <label for="login-password">Password</label>
          <input
            id="login-password"
            type="password"
            bind:value={loginPassword}
            autocomplete="current-password"
            required
          />
          {#if loginError}
            <p class="login-error" role="alert">{loginError}</p>
          {/if}
          <button class="button button-primary login-button" type="submit" disabled={loginPending}>
            {loginPending ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <p class="credential-hint">
          Demo credentials: <strong>user</strong> / <strong>password</strong>
        </p>
      </section>
    </main>
  {:else}
    <main class="workspace">
      <section class="intro" aria-labelledby="page-title">
        <div>
          <p class="eyebrow">Project workspace <span>•</span> Spring launch</p>
          <h1 id="page-title">Make the next move.</h1>
          <p class="intro-copy">
            A clear view of the work in motion, one thoughtful step at a time.
          </p>
        </div>
        <div
          class="board-summary"
          aria-label={`${cardCount} cards across ${columns.length} columns`}
        >
          <span class="summary-number">{cardCount}</span>
          <span class="summary-label">active cards</span>
        </div>
      </section>

      <div class="toolbar">
        <div class="toolbar-label"><span class="yellow-dot"></span> Your board</div>
        <p>Drag cards to move them, or use the move menu on each card.</p>
      </div>

      {#if boardPending}
        <p aria-live="polite">Loading your board…</p>
      {/if}
      {#if boardError}
        <p class="login-error" role="alert">{boardError}</p>
      {/if}
      <section class="board" aria-label="Kanban board">
        {#each columns as column (column.id)}
          <article
            class:drop-target={draggedCardId !== null}
            class="column"
            ondragover={(event) => event.preventDefault()}
            ondrop={(event) => handleDrop(event, column.id)}
          >
            <header class="column-header">
              {#if editingColumnId === column.id}
                <form
                  class="rename-form"
                  onsubmit={(event) => {
                    event.preventDefault();
                    saveColumnName(column);
                  }}
                >
                  <label class="sr-only" for={`rename-${column.id}`}>Column name</label>
                  <input id={`rename-${column.id}`} bind:value={draftColumnName} maxlength="28" />
                  <button
                    class="icon-button confirm"
                    type="submit"
                    aria-label="Save column name"
                    disabled={savingAction !== null}>✓</button
                  >
                  <button
                    class="icon-button"
                    type="button"
                    aria-label="Cancel rename"
                    onclick={() => (editingColumnId = null)}>×</button
                  >
                </form>
              {:else}
                <div class="column-title-row">
                  <h2>{column.name}</h2>
                  <button
                    class="icon-button"
                    type="button"
                    aria-label={`Rename ${column.name} column`}
                    onclick={() => startRename(column)}>•••</button
                  >
                </div>
              {/if}
              <span class="count-badge">{column.cards.length}</span>
            </header>

            <div class="card-list" aria-label={`${column.name} cards`}>
              {#each column.cards as card (card.id)}
                <article
                  class:dragging={draggedCardId === card.id}
                  class="task-card"
                  draggable="true"
                  ondragstart={(event) => handleDragStart(event, card.id)}
                  ondragend={handleDragEnd}
                >
                  {#if editingCardId === card.id}
                    <form
                      class="edit-card-form"
                      onsubmit={(event) => {
                        event.preventDefault();
                        saveCard(card.id);
                      }}
                    >
                      <label for={`edit-title-${card.id}`}>Title</label>
                      <input
                        id={`edit-title-${card.id}`}
                        bind:value={draftTitle}
                        maxlength="80"
                        required
                      />
                      <label for={`edit-details-${card.id}`}>Details</label>
                      <textarea
                        id={`edit-details-${card.id}`}
                        bind:value={draftDetails}
                        rows="3"
                        maxlength="240"></textarea>
                      <div class="form-actions">
                        <button
                          class="button button-primary"
                          type="submit"
                          disabled={savingAction === `card:${card.id}`}
                          >{savingAction === `card:${card.id}` ? 'Saving…' : 'Save'}</button
                        >
                        <button
                          class="button button-quiet"
                          type="button"
                          onclick={() => (editingCardId = null)}>Cancel</button
                        >
                      </div>
                    </form>
                  {:else}
                    <div class="card-topline">
                      <span class="card-grip" aria-hidden="true">⠿</span>
                      <button
                        class="card-menu"
                        type="button"
                        aria-label={`Edit ${card.title}`}
                        onclick={() => startEditCard(card.id)}>Edit</button
                      >
                    </div>
                    <h3>{card.title}</h3>
                    <p>{card.details}</p>
                    <div class="card-footer">
                      <span class="card-tag">Task</span>
                      <div class="card-actions">
                        <label class="sr-only" for={`move-${card.id}`}>Move {card.title} to</label>
                        <select
                          id={`move-${card.id}`}
                          class="move-select"
                          value={column.id}
                          aria-label={`Move ${card.title} to`}
                          disabled={savingAction === `move:${card.id}`}
                          onchange={(event) => moveCard(card.id, event.currentTarget.value)}
                        >
                          {#each columns as destination (destination.id)}
                            <option value={destination.id}>{destination.name}</option>
                          {/each}
                        </select>
                        <button
                          class="delete-button"
                          type="button"
                          disabled={savingAction === `delete:${card.id}`}
                          onclick={() => deleteCard(card.id)}>Delete</button
                        >
                      </div>
                    </div>
                  {/if}
                </article>
              {/each}
              {#if column.cards.length === 0}
                <div class="empty-column">
                  <span>✦</span>
                  <p>Drop a card here</p>
                </div>
              {/if}
            </div>

            {#if newCardColumnId === column.id}
              <form
                class="new-card-form"
                onsubmit={(event) => {
                  event.preventDefault();
                  addCard(column);
                }}
              >
                <label for={`new-title-${column.id}`}>Title</label>
                <input
                  id={`new-title-${column.id}`}
                  bind:value={newTitle}
                  placeholder="What needs doing?"
                  maxlength="80"
                  required
                />
                <label for={`new-details-${column.id}`}>Details <span>(optional)</span></label>
                <textarea
                  id={`new-details-${column.id}`}
                  bind:value={newDetails}
                  placeholder="Add useful context"
                  rows="3"
                  maxlength="240"></textarea>
                <div class="form-actions">
                  <button
                    class="button button-primary"
                    type="submit"
                    disabled={savingAction === `new:${column.id}`}
                    >{savingAction === `new:${column.id}` ? 'Adding…' : 'Add card'}</button
                  >
                  <button
                    class="button button-quiet"
                    type="button"
                    onclick={() => (newCardColumnId = null)}>Cancel</button
                  >
                </div>
              </form>
            {:else}
              <button class="add-card" type="button" onclick={() => openNewCard(column.id)}
                ><span>+</span> Add card</button
              >
            {/if}
          </article>
        {/each}
      </section>
    </main>
  {/if}

  <p class="sr-only" aria-live="polite">{statusMessage}</p>
</div>
