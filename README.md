# Context-Aware Rate Limiter

A small FastAPI service demonstrating in-memory, per-user rate limiting by user tier and logical endpoint type.

## Rate-limit rules

| User tier | Endpoint type | Limit | Window |
|---|---|---:|---:|
| free | ai/heavy | 5 requests | 60 seconds |
| free | read/light | 30 requests | 60 seconds |
| paid | ai/heavy | 30 requests | 60 seconds |
| paid | read/light | 120 requests | 60 seconds |

The endpoint category is assigned using `@rate_limit("ai")` or `@rate_limit("read")`; it is not inferred from the URL. The middleware uses the matched route's tag.

## Run locally

Python 3.9+ is required.

```bash
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation.

## Example requests

```bash
curl http://127.0.0.1:8000/data/items -H "X-User-ID: user-123"
curl -X POST http://127.0.0.1:8000/ai/generate -H "X-User-ID: user-123" -H "Content-Type: application/json" -d '{"prompt":"hello"}'
curl -X POST http://127.0.0.1:8000/ai/generate -H "X-User-ID: subscriber-1" -H "X-User-Tier: paid" -H "Content-Type: application/json" -d '{"prompt":"hello"}'
```

- `X-User-ID` identifies the caller. Missing IDs share the `anonymous` bucket.
- `X-User-Tier` accepts `free` or `paid`; missing/invalid values default to `free`.
- A blocked request returns HTTP 429, a JSON error body, and a `Retry-After` header.
- `X-RateLimit-Limit` is returned on allowed tagged-route responses.

## Run tests

```bash
pytest -q
```

## Deployment

Use a Python web service host that supports a `Procfile` or configure the start command directly:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Set the service's health-check path to `/health` if supported. After deployment, test `/health`, `/docs`, and the rate-limited endpoints. Paste the **live service URL** into the assessment's deployment-link field only after verifying it works.

## Important limitations

This is intentionally in-memory as required: state resets when the process restarts and is not shared between multiple worker instances. For production multi-instance deployments, shared storage would normally be required, but adding a database or Redis would violate this assessment's stated constraints.
