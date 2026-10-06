import os
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.openrouter import OPENROUTER_MODEL, OpenRouterClient


def make_client(tmp_path: Path, openrouter_client: OpenRouterClient | None = None) -> TestClient:
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir(parents=True)
    (frontend_dir / "index.html").write_text("<html>home</html>")
    return TestClient(create_app(frontend_dir, tmp_path / "app.db", openrouter_client))


def login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert response.status_code == 200


def test_connectivity_requires_authentication(tmp_path: Path) -> None:
    with make_client(tmp_path, OpenRouterClient(api_key="secret")) as client:
        response = client.post("/api/openrouter/connectivity")

    assert response.status_code == 401


def test_connectivity_sends_server_side_request_and_returns_safe_result(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "4"}}]},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    with make_client(tmp_path, OpenRouterClient(api_key="server-secret", transport=transport)) as client:
        login(client)
        response = client.post("/api/openrouter/connectivity")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "model": OPENROUTER_MODEL, "answer": "4"}
    assert len(requests) == 1
    assert requests[0].url == "https://openrouter.ai/api/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer server-secret"
    assert requests[0].content.decode().find(OPENROUTER_MODEL) >= 0
    assert "server-secret" not in response.text


def test_missing_api_key_is_reported_without_making_a_request(tmp_path: Path) -> None:
    with make_client(tmp_path, OpenRouterClient(api_key="")) as client:
        login(client)
        response = client.post("/api/openrouter/connectivity")

    assert response.status_code == 503
    assert response.json() == {"detail": "OpenRouter is not configured"}


def test_timeout_is_mapped_to_gateway_timeout(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with make_client(
        tmp_path,
        OpenRouterClient(api_key="secret", transport=httpx.MockTransport(handler)),
    ) as client:
        login(client)
        response = client.post("/api/openrouter/connectivity")

    assert response.status_code == 504
    assert response.json() == {"detail": "OpenRouter request timed out"}


def test_upstream_and_invalid_responses_are_mapped_safely(tmp_path: Path) -> None:
    def upstream_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"error": {"message": "private provider detail"}},
            request=request,
        )

    with make_client(
        tmp_path / "upstream",
        OpenRouterClient(api_key="secret", transport=httpx.MockTransport(upstream_handler)),
    ) as client:
        login(client)
        upstream = client.post("/api/openrouter/connectivity")

    assert upstream.status_code == 502
    assert upstream.json() == {"detail": "OpenRouter returned an upstream error"}
    assert "private provider detail" not in upstream.text

    def invalid_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []}, request=request)

    with make_client(
        tmp_path / "invalid",
        OpenRouterClient(api_key="secret", transport=httpx.MockTransport(invalid_handler)),
    ) as client:
        login(client)
        invalid = client.post("/api/openrouter/connectivity")

    assert invalid.status_code == 502
    assert invalid.json() == {"detail": "OpenRouter returned an invalid response"}


@pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY"),
    reason="Set OPENROUTER_API_KEY to run the optional live connectivity test",
)
def test_live_connectivity() -> None:
    answer = OpenRouterClient().complete("What is 2 + 2? Reply with only the number.")
    assert answer
