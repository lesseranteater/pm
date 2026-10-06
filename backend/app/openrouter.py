from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, status


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-oss-120b"
DEFAULT_TIMEOUT_SECONDS = 30.0


class OpenRouterError(Exception):
    """An expected failure while calling or decoding the OpenRouter response."""

    def __init__(self, message: str, http_status: int):
        super().__init__(message)
        self.http_status = http_status


class OpenRouterClient:
    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY", "")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def complete(self, prompt: str) -> str:
        if not self.api_key:
            raise OpenRouterError("OpenRouter is not configured", status.HTTP_503_SERVICE_UNAVAILABLE)

        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 128,
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.post(
                    OPENROUTER_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as error:
            raise OpenRouterError("OpenRouter request timed out", status.HTTP_504_GATEWAY_TIMEOUT) from error
        except httpx.RequestError as error:
            raise OpenRouterError("OpenRouter is unavailable", status.HTTP_502_BAD_GATEWAY) from error

        if response.is_error:
            raise OpenRouterError("OpenRouter returned an upstream error", status.HTTP_502_BAD_GATEWAY)

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise OpenRouterError("OpenRouter returned an invalid response", status.HTTP_502_BAD_GATEWAY) from error
        if not isinstance(content, str) or not content.strip():
            raise OpenRouterError("OpenRouter returned an invalid response", status.HTTP_502_BAD_GATEWAY)
        return content.strip()


def register_openrouter_routes(
    app: FastAPI,
    require_user: Callable[..., dict[str, str]],
    client: OpenRouterClient,
) -> None:
    @app.post("/api/openrouter/connectivity", tags=["openrouter"])
    def connectivity(_: dict[str, str] = Depends(require_user)) -> dict[str, Any]:
        try:
            answer = client.complete("What is 2 + 2? Reply with only the number.")
        except OpenRouterError as error:
            raise HTTPException(status_code=error.http_status, detail=str(error)) from error
        return {"ok": True, "model": OPENROUTER_MODEL, "answer": answer}
