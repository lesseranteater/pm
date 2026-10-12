import pytest

from backend.app.errors import UserFacingError
from backend.app.jira_rules import is_semantic_release_version, jql_project, jql_quote


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Deploy.ai-data.26.4.1", True),
        ("hotfix.core-dev-3-Sport.26.3.10.2", True),
        ("UNKNOWN", False),
        ("Deploy.ai-data.26.5.1", False),
        ("Deploy.unknown-team.26.4.1", False),
        ("Deploy.ai-data.26.4.1; DROP", False),
    ],
)
def test_semantic_release_version_names(name: str, expected: bool) -> None:
    assert is_semantic_release_version(name) is expected


def test_jql_quote_escapes_quotes_and_backslashes() -> None:
    assert jql_quote("plain") == '"plain"'
    assert jql_quote('a" OR project = X OR fixVersion = "b') == '"a\\" OR project = X OR fixVersion = \\"b"'
    backslash = chr(92)
    assert jql_quote("back" + backslash + "slash") == '"back' + backslash * 2 + 'slash"'


@pytest.mark.parametrize("key", ["IGM", "AB", "A1_B2"])
def test_jql_project_accepts_plain_keys(key: str) -> None:
    assert jql_project(key) == key


@pytest.mark.parametrize("key", ["igm", "I", "IGM OR project = X", 'IGM"', "IGM\n", ""])
def test_jql_project_rejects_anything_else(key: str) -> None:
    with pytest.raises(UserFacingError):
        jql_project(key)
