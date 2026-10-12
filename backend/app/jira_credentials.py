"""Request-scoped Jira credentials; the URL remains server configuration."""

import os
from contextvars import ContextVar

from dotenv import load_dotenv
from jira import JIRA

from .main_paths import PROJECT_ROOT

JIRA_TOKEN_COOKIE = "pm_jira_token"
jira_token: ContextVar[str] = ContextVar("jira_token", default="")


def jira_token_configured() -> bool:
    return bool(jira_token.get())


def create_jira_client() -> JIRA:
    load_dotenv(PROJECT_ROOT / ".env")
    token = jira_token.get()
    if not token:
        raise RuntimeError("Enter your Jira token after signing in.")
    return JIRA(
        server=os.getenv("JIRA_URL", "https://jira.egt-digital.com"),
        token_auth=token,
    )
