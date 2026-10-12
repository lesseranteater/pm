<script lang="ts">
  type Props = {
    open?: boolean;
    title: string;
    message: string;
    confirmLabel: string;
    onconfirm: () => void;
    oncancel?: () => void;
  };

  let {
    open = $bindable(false),
    title,
    message,
    confirmLabel,
    onconfirm,
    oncancel
  }: Props = $props();

  let dialog: HTMLDialogElement | undefined = $state();
  let cancelButton: HTMLButtonElement | undefined = $state();
  // Each time the dialog opens it can be answered once, however it ends up closing.
  let answered = true;

  $effect(() => {
    if (!dialog) return;
    if (open && !dialog.open) {
      answered = false;
      dialog.showModal();
      // Start on Cancel, so pressing Enter by reflex never confirms a live action.
      cancelButton?.focus();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  });

  function answer(confirmed: boolean) {
    if (answered) return;
    answered = true;
    open = false;
    if (confirmed) onconfirm();
    else oncancel?.();
  }
</script>

<!-- The button and Escape handlers answer directly; the close event is only a safety net. -->
<dialog
  bind:this={dialog}
  class="confirm-dialog"
  aria-labelledby="confirm-dialog-title"
  aria-describedby="confirm-dialog-message"
  oncancel={(event) => {
    event.preventDefault();
    answer(false);
  }}
  onclose={() => answer(false)}
>
  <h2 id="confirm-dialog-title">{title}</h2>
  <p id="confirm-dialog-message">{message}</p>
  <div class="confirm-actions">
    <button
      type="button"
      class="button-secondary"
      bind:this={cancelButton}
      onclick={() => answer(false)}
    >
      Cancel
    </button>
    <button type="button" class="danger" onclick={() => answer(true)}>{confirmLabel}</button>
  </div>
</dialog>
