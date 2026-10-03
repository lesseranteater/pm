<script lang="ts">
  import { resolve } from '$app/paths';
  import { createCard, createDemoBoard, type Card, type Column } from '$lib/board';

  let columns = $state<Column[]>(createDemoBoard());
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

  function saveCard(cardId: string) {
    const result = findCard(cardId);
    const title = draftTitle.trim();
    if (!result || !title) return;
    result.card.title = title;
    result.card.details = draftDetails.trim();
    editingCardId = null;
    statusMessage = `Updated ${title}`;
  }

  function deleteCard(cardId: string) {
    const result = findCard(cardId);
    if (!result) return;
    result.column.cards = result.column.cards.filter((card) => card.id !== cardId);
    if (editingCardId === cardId) editingCardId = null;
    statusMessage = `Deleted ${result.card.title}`;
  }

  function startRename(column: Column) {
    editingColumnId = column.id;
    draftColumnName = column.name;
  }

  function saveColumnName(column: Column) {
    const name = draftColumnName.trim();
    if (!name) return;
    column.name = name;
    editingColumnId = null;
    statusMessage = `Renamed column to ${name}`;
  }

  function openNewCard(columnId: string) {
    newCardColumnId = columnId;
    newTitle = '';
    newDetails = '';
  }

  function addCard(column: Column) {
    const title = newTitle.trim();
    if (!title) return;
    column.cards = [...column.cards, createCard(title, newDetails)];
    newCardColumnId = null;
    statusMessage = `Added ${title} to ${column.name}`;
  }

  function moveCard(cardId: string, destinationId: string) {
    const result = findCard(cardId);
    const destination = columns.find((column) => column.id === destinationId);
    if (!result || !destination || result.column.id === destinationId) return;
    result.column.cards = result.column.cards.filter((card) => card.id !== cardId);
    destination.cards = [...destination.cards, result.card];
    statusMessage = `Moved ${result.card.title} to ${destination.name}`;
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
      <span class="live-indicator"><span></span> Local workspace</span>
      <span class="avatar" aria-label="Signed in as Alex">A</span>
    </div>
  </header>

  <main class="workspace">
    <section class="intro" aria-labelledby="page-title">
      <div>
        <p class="eyebrow">Project workspace <span>•</span> Spring launch</p>
        <h1 id="page-title">Make the next move.</h1>
        <p class="intro-copy">A clear view of the work in motion, one thoughtful step at a time.</p>
      </div>
      <div class="board-summary" aria-label={`${cardCount} cards across ${columns.length} columns`}>
        <span class="summary-number">{cardCount}</span>
        <span class="summary-label">active cards</span>
      </div>
    </section>

    <div class="toolbar">
      <div class="toolbar-label"><span class="yellow-dot"></span> Your board</div>
      <p>Drag cards to move them, or use the move menu on each card.</p>
    </div>

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
                <button class="icon-button confirm" type="submit" aria-label="Save column name"
                  >✓</button
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
                      <button class="button button-primary" type="submit">Save</button>
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
                        onchange={(event) => moveCard(card.id, event.currentTarget.value)}
                      >
                        {#each columns as destination (destination.id)}
                          <option value={destination.id}>{destination.name}</option>
                        {/each}
                      </select>
                      <button
                        class="delete-button"
                        type="button"
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
                <button class="button button-primary" type="submit">Add card</button>
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

  <p class="sr-only" aria-live="polite">{statusMessage}</p>
</div>
