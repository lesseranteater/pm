import pytest
from jira.exceptions import JIRAError
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout

from backend.app.errors import ProjectNotFoundError, explain_exception


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (JIRAError(status_code=401, text="bad token"), "Jira rejected the access token (HTTP 401)"),
        (JIRAError(status_code=403, text="no"), "Jira denied access (HTTP 403)"),
        (JIRAError(status_code=404, text="gone"), "Jira could not find what was requested (HTTP 404)"),
        (JIRAError(status_code=502, text="bad gateway"), "Jira reported a server error (HTTP 502)"),
        (JIRAError(status_code=418, text="teapot"), "Jira returned an error (HTTP 418)"),
        (JIRAError(status_code=None, text="no response"), "Could not reach Jira"),
        (RequestsConnectionError("boom"), "Could not reach Jira"),
        (Timeout("slow"), "Could not reach Jira"),
        (RuntimeError("JIRA_TOKEN environment variable is not configured"), "Add JIRA_TOKEN"),
        (ProjectNotFoundError("Jira project 'ABC' was not found."), "Jira project 'ABC' was not found."),
        (ValueError("anything"), "Unexpected error (ValueError)"),
    ],
)
def test_failures_are_explained_in_plain_language(error: BaseException, expected: str) -> None:
    assert expected in explain_exception(error)


def test_explanations_never_leak_the_underlying_message() -> None:
    explanation = explain_exception(RequestsConnectionError("https://user:secret@host"))

    assert "secret" not in explanation
