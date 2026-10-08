"""Turn low-level failures into messages a person can act on."""

from __future__ import annotations

from jira.exceptions import JIRAError
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout


class ProjectNotFoundError(RuntimeError):
    """Raised when Jira has no project with the requested key."""


UNREACHABLE_MESSAGE = "Could not reach Jira. Check your network or VPN connection and try again."


def explain_exception(error: BaseException) -> str:
    """Return a short, safe explanation of why a Jira operation failed.

    The explanation never includes tokens, URLs with credentials, or tracebacks.
    """
    if isinstance(error, ProjectNotFoundError):
        return str(error)

    if isinstance(error, JIRAError):
        status = error.status_code
        if status is None:
            return UNREACHABLE_MESSAGE
        if status == 401:
            return (
                "Jira rejected the access token (HTTP 401). Check that JIRA_TOKEN in the "
                ".env file is valid and has not expired."
            )
        if status == 403:
            return "Jira denied access (HTTP 403). The token does not have permission for this action."
        if status == 404:
            return "Jira could not find what was requested (HTTP 404)."
        if status >= 500:
            return f"Jira reported a server error (HTTP {status}). Try again shortly."
        return f"Jira returned an error (HTTP {status})."

    if isinstance(error, (RequestsConnectionError, Timeout)):
        return UNREACHABLE_MESSAGE

    if isinstance(error, RuntimeError) and "JIRA_TOKEN" in str(error):
        return (
            "Jira access is not configured. Add JIRA_TOKEN to the .env file and restart the server."
        )

    return f"Unexpected error ({type(error).__name__}). See the server log for details."
