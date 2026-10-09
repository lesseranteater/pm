"""Run ``tools/release_check.py`` and stream its printed report as a Script Log."""

from __future__ import annotations

import importlib.util
import io
import logging
from contextlib import redirect_stdout
from pathlib import Path
from threading import Lock
from typing import Iterator

from .main_paths import PROJECT_ROOT
from .script_runner import stream_script_log

log = logging.getLogger("release-check")
log.setLevel(logging.INFO)
log.propagate = False

release_check_lock = Lock()
_SCRIPT_PATH = PROJECT_ROOT / "tools" / "release_check.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("release_check_tool", _SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Release Check script could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _release_check(deployment_plan_key: str) -> None:
    script = _load_script()
    output = io.StringIO()
    with redirect_stdout(output):
        script.find_mismatching_version_sources(script.jira, deployment_plan_key)

    for line in output.getvalue().splitlines():
        log.info("%s", line)


def stream_release_check(deployment_plan_key: str) -> Iterator[str]:
    """Check a deployment plan without changing Jira and stream the report."""
    return stream_script_log(
        log,
        release_check_lock,
        lambda: _release_check(deployment_plan_key),
        "Release check failed.",
    )
