import logging
import threading

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
        raise RuntimeError("JIRA_TOKEN environment variable is not configured")

    output = "".join(stream_script_log(logger, threading.Lock(), work, "Run failed."))

    assert "| ERROR | Cause: Jira access is not configured." in output
    assert "| ERROR | Run failed." in output
    assert "RuntimeError" in output
    assert logger.handlers == []


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
