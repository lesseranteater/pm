import { LogTracker, type LogCounts, type LogLine } from '$lib/script-log';
import { ApiError } from '$lib/stream';

export type RunStatus = 'idle' | 'running' | 'done' | 'failed';

export type RunOptions = {
  /** What was run, for example "Dry run, IGM, up to 7 October 2026". */
  description: string;
  /** Identifies the inputs, so a page can tell when they have changed since this run. */
  signature: string;
  dryRun: boolean;
};

function describeFailure(failure: unknown): string {
  if (failure instanceof ApiError) {
    return failure.detail || `The server rejected the request (HTTP ${failure.status}).`;
  }
  if (failure instanceof TypeError) {
    return 'Could not reach the server. Check that it is still running, then try again.';
  }
  return 'Something went wrong while running the script.';
}

/** The state of one script run, shared by the page that starts it and its log. */
export class ScriptRun {
  log = $state('');
  /** Parsed from `log` as it streams, so the page never rescans the whole log. */
  lines = $state.raw<LogLine[]>([]);
  counts = $state.raw<LogCounts>({ entries: 0, warnings: 0, errors: 0 });
  #tracker = new LogTracker();
  status = $state<RunStatus>('idle');
  error = $state('');
  startedAt = $state(0);
  finishedAt = $state(0);
  description = $state('');
  signature = $state('');
  dryRun = $state(true);

  get running(): boolean {
    return this.status === 'running';
  }

  /** The run finished and its log holds no errors. Warnings are expected and allowed. */
  get succeeded(): boolean {
    return this.status === 'done' && this.counts.errors === 0;
  }

  #publish(): void {
    this.lines = this.#tracker.lines.slice();
    this.counts = { ...this.#tracker.counts };
  }

  async start(
    options: RunOptions,
    execute: (onText: (text: string) => void) => Promise<void>
  ): Promise<void> {
    if (this.running) return;

    this.log = '';
    this.#tracker = new LogTracker();
    this.#publish();
    this.error = '';
    this.description = options.description;
    this.signature = options.signature;
    this.dryRun = options.dryRun;
    this.finishedAt = 0;
    this.startedAt = Date.now();
    this.status = 'running';

    try {
      await execute((text) => {
        this.log += text;
        this.#tracker.append(text);
        this.#publish();
      });
      this.status = 'done';
    } catch (failure) {
      this.error = describeFailure(failure);
      this.status = 'failed';
    } finally {
      this.#tracker.flush();
      this.#publish();
      this.finishedAt = Date.now();
    }
  }
}
