"""Run a script on a worker thread and stream its log as it is written."""

from __future__ import annotations

import logging
import queue
import threading
from contextvars import copy_context
from typing import Callable, Iterator

from .errors import explain_exception

server_log = logging.getLogger(__name__)
# How long a queued run waits for the one in front of it before giving up.
LOCK_WAIT_SECONDS = 15 * 60
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"
_FINISHED = object()


class _QueueHandler(logging.Handler):
    """Puts each formatted log record on a queue, one chunk per record."""

    def __init__(self, destination: "queue.Queue[object]") -> None:
        super().__init__()
        self._destination = destination
        self.setFormatter(logging.Formatter(LOG_FORMAT))

    def emit(self, record: logging.LogRecord) -> None:
        self._destination.put(self.format(record) + "\n")


def stream_script_log(
    logger: logging.Logger,
    lock: threading.Lock,
    work: Callable[[], None],
    failure_message: str,
    wait_timeout: float = LOCK_WAIT_SECONDS,
) -> Iterator[str]:
    """Yield the log lines of ``work`` as they are written.

    The workflows change shared Jira state and use a module-level logger, so only one
    runs at a time. A second caller is told it is waiting instead of looking stuck, and
    gives up after ``wait_timeout`` seconds so a stuck run cannot hold callers forever.
    Failures never escape: they are explained in the log, so the stream always ends
    normally and the caller sees exactly what happened.

    If the caller disconnects while still queued, the run never starts. If it disconnects
    after the run has started, the run completes anyway: stopping a release or archive
    half-way is worse than finishing it. Its output is then dropped, and the result queue is
    deliberately unbounded so a slow client can never block a run that holds the lock.
    """
    chunks: "queue.Queue[object]" = queue.Queue()
    handler = _QueueHandler(chunks)
    decision = threading.Lock()  # guards the two flags below
    started = False
    abandoned = False

    def say(level: int, message: str) -> None:
        chunks.put(
            handler.format(
                logging.makeLogRecord(
                    {"levelname": logging.getLevelName(level), "levelno": level, "msg": message}
                )
            )
            + "\n"
        )

    def run() -> None:
        nonlocal started
        acquired = lock.acquire(blocking=False)
        if not acquired:
            say(logging.WARNING, "Another run is in progress. Waiting for it to finish...")
            acquired = lock.acquire(timeout=wait_timeout)
        if not acquired:
            say(
                logging.ERROR,
                f"Another run is still in progress after {int(wait_timeout // 60)} minute(s). "
                "Nothing was started. Try again once it has finished.",
            )
            chunks.put(_FINISHED)
            return
        try:
            with decision:
                if abandoned:
                    server_log.info("Queued run skipped: the client disconnected before it started")
                    return
                started = True
            logger.addHandler(handler)
            try:
                work()
            except Exception as error:
                # The traceback can hold URLs and Jira response bodies, so it stays in the server log.
                server_log.exception(failure_message)
                logger.error("Cause: %s", explain_exception(error))
                logger.error(failure_message)
            finally:
                logger.removeHandler(handler)
        finally:
            lock.release()
            chunks.put(_FINISHED)

    context = copy_context()
    threading.Thread(target=lambda: context.run(run), daemon=True).start()

    finished = False
    try:
        while True:
            chunk = chunks.get()
            if chunk is _FINISHED:
                finished = True
                return
            yield str(chunk)
    finally:
        if not finished:
            with decision:
                if started:
                    server_log.info("Client disconnected mid-run; the run continues to completion")
                else:
                    abandoned = True
