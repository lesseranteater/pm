# OpenRouter Connectivity

The backend keeps `OPENROUTER_API_KEY` server-side and uses the OpenRouter chat
completions endpoint with model `openai/gpt-oss-120b`. The key is never returned
by an API route or included in frontend code.

## Configuration

Set the key in the FastAPI process environment:

```bash
export OPENROUTER_API_KEY=...
```

The default request timeout is 30 seconds. A missing key returns `503`; timeout
and upstream failures return safe `504` and `502` responses respectively.

## Connectivity Check

After authenticating, call the backend-only connectivity operation:

```bash
curl -X POST \
  -H 'Cookie: pm_session=...' \
  http://127.0.0.1:8000/api/openrouter/connectivity
```

It sends the prompt `What is 2 + 2? Reply with only the number.` and returns the
model identifier and response text without exposing upstream response details.

The default test suite mocks OpenRouter. The live test is opt-in:

```bash
OPENROUTER_API_KEY=... uv run pytest backend/tests/test_openrouter.py -k live
```
