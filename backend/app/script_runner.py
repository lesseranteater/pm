"""Run a script on a worker thread and stream its log as it is written."""

from __future__ import annotations

import logging
import queue
import threading
from typing import Callable, Iterator

from .errors import explain_exception

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
) -> Iterator[str]:
    """Yield the log lines of ``work`` as they are written.

    The workflows change shared Jira state and use a module-level logger, so only one
    runs at a time. A second caller is told it is waiting instead of looking stuck.
    Failures never escape: they are explained in the log, so the stream always ends
    normally and the caller sees exactly what happened.
    """
    chunks: "queue.Queue[object]" = queue.Queue()
    handler = _QueueHandler(chunks)

    def run() -> None:
        if not lock.acquire(blocking=False):
            chunks.put(
                handler.format(
                    logging.makeLogRecord(
                        {
                            "levelname": "WARNING",
                            "levelno": logging.WARNING,
                            "msg": "Another run is in progress. Waiting for it to finish...",
                        }
                    )
                )
                + "\n"
            )
            lock.acquire()
        try:
            logger.addHandler(handler)
            try:
                work()
            except Exception as error:
                logger.error("Cause: %s", explain_exception(error))
                logger.exception(failure_message)
            finally:
                logger.removeHandler(handler)
        finally:
            lock.release()
            chunks.put(_FINISHED)

    threading.Thread(target=run, daemon=True).start()

    while True:
        chunk = chunks.get()
        if chunk is _FINISHED:
            return
        yield str(chunk)
