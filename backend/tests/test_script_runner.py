import logging
import threading
import time

from jira.exceptions import JIRAError

from backend.app.errors import UserFacingError
from backend.app.script_runner import stream_script_log


def make_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()
    return logger


def test_lines_are_yielded_while_the_work_is_still_running() -> None:
    logger = make_logger("test-runner-streaming")
    release_work = threading.Event()

    def work() -> None:
        logger.info("first")
        assert release_work.wait(timeout=5)
        logger.info("second")

    stream = stream_script_log(logger, threading.Lock(), work, "failed")

    first = next(stream)
    assert first.endswith("| INFO | first\n")
    release_work.set()
    assert list(stream)[0].endswith("| INFO | second\n")
    assert logger.handlers == []


def test_a_failure_is_explained_in_the_log_and_the_stream_ends_normally() -> None:
    logger = make_logger("test-runner-failure")

    def work() -> None:
        raise UserFacingError("Enter your Jira token after signing in.")

    output = "".join(stream_script_log(logger, threading.Lock(), work, "Run failed."))

    assert "| ERROR | Cause: Enter your Jira token after signing in." in output
    assert "| ERROR | Run failed." in output
    assert logger.handlers == []


def test_the_stream_never_carries_a_traceback_or_the_jira_response() -> None:
    logger = make_logger("test-runner-no-traceback")

    def work() -> None:
        raise JIRAError(
            status_code=500, url="https://jira.internal/rest/api/2/x", text="<html>internal body</html>"
        )

    output = "".join(stream_script_log(logger, threading.Lock(), work, "Run failed."))

    assert "Jira reported a server error (HTTP 500)" in output
    for leaked in ("Traceback", "jira.internal", "internal body", "script_runner.py"):
        assert leaked not in output


def test_a_second_run_says_it_is_waiting_for_the_first() -> None:
    logger = make_logger("test-runner-waiting")
    lock = threading.Lock()
    first_started = threading.Event()
    let_first_finish = threading.Event()

    def first_work() -> None:
        logger.info("first running")
        first_started.set()
        assert let_first_finish.wait(timeout=5)

    first = stream_script_log(logger, lock, first_work, "failed")
    assert "first running" in next(first)
    assert first_started.wait(timeout=5)

    second = stream_script_log(logger, lock, lambda: logger.info("second ran"), "failed")
    waiting = next(second)
    assert "| WARNING | Another run is in progress." in waiting

    let_first_finish.set()
    assert list(first) == []
    assert any("second ran" in line for line in second)


def test_a_queued_run_gives_up_after_the_wait_timeout_without_starting() -> None:
    logger = make_logger("test-runner-timeout")
    lock = threading.Lock()
    lock.acquire()  # another run holds it and never finishes
    ran: list[str] = []

    output = list(
        stream_script_log(logger, lock, lambda: ran.append("work"), "failed", wait_timeout=0.2)
    )

    assert "| WARNING | Another run is in progress." in output[0]
    assert "| ERROR | Another run is still in progress" in output[1]
    assert "Nothing was started" in output[1]
    assert ran == []
    assert lock.locked()  # still the other run's lock, never released by us


def test_a_queued_run_whose_client_left_never_starts() -> None:
    logger = make_logger("test-runner-abandoned-queue")
    lock = threading.Lock()
    lock.acquire()
    ran: list[str] = []

    stream = stream_script_log(logger, lock, lambda: ran.append("work"), "failed")
    assert "Another run is in progress" in next(stream)
    stream.close()  # the client disconnects while queued
    lock.release()

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and not lock.acquire(blocking=False):
        time.sleep(0.01)
    else:
        lock.release()
    time.sleep(0.2)
    assert ran == []


def test_a_started_run_completes_even_if_the_client_disconnects() -> None:
    logger = make_logger("test-runner-abandoned-run")
    release_work = threading.Event()
    finished = threading.Event()

    def work() -> None:
        logger.info("started")
        assert release_work.wait(timeout=5)
        finished.set()

    stream = stream_script_log(logger, threading.Lock(), work, "failed")
    assert "started" in next(stream)
    stream.close()  # the client disconnects mid-run
    release_work.set()

    assert finished.wait(timeout=5)
