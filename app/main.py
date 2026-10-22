from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match
from time import monotonic
from threading import Lock
from typing import Callable

app = FastAPI(title="Context-Aware Rate Limiter", version="1.0.0")

# Limits are (maximum requests, window length in seconds).
RATE_LIMITS = {
    "free": {"ai": (5, 60), "read": (30, 60)},
    "paid": {"ai": (30, 60), "read": (120, 60)},
}


def rate_limit(endpoint_type: str) -> Callable:
    """Tag a route with its logical rate-limit category, independent of its URL."""
    if endpoint_type not in {"ai", "read"}:
        raise ValueError("endpoint_type must be 'ai' or 'read'")

    def decorator(func: Callable) -> Callable:
        func.rate_limit_type = endpoint_type
        return func
    return decorator


class InMemoryRateLimiter:
    def __init__(self):
        self._buckets: dict[tuple[str, str, str], list[float | int]] = {}
        self._lock = Lock()

    def check(self, user_id: str, tier: str, endpoint_type: str) -> tuple[bool, int, int]:
        limit, window = RATE_LIMITS[tier][endpoint_type]
        now = monotonic()
        key = (user_id, tier, endpoint_type)

        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None or now - float(bucket[1]) >= window:
                bucket = [0, now]
                self._buckets[key] = bucket

            count = int(bucket[0])
            if count >= limit:
                retry_after = max(1, int(window - (now - float(bucket[1])) + 0.999))
                return False, limit, retry_after

            bucket[0] = count + 1
            return True, limit, 0


limiter = InMemoryRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Find the matched route and read its explicit tag; do not infer type from URL.
        endpoint_type = None
        try:
            for route in request.app.router.routes:
                match, _ = route.matches(request.scope)
                if match == Match.FULL:
                    endpoint_type = getattr(getattr(route, "endpoint", None),
                                            "rate_limit_type", None)
                    break
        except Exception:
            endpoint_type = None

        # Untagged routes (health/docs/etc.) are not rate limited.
        if endpoint_type is None:
            return await call_next(request)

        user_id = request.headers.get("X-User-ID", "").strip() or "anonymous"
        requested_tier = request.headers.get("X-User-Tier", "free").strip().lower()
        tier = requested_tier if requested_tier in RATE_LIMITS else "free"

        allowed, limit, retry_after = limiter.check(user_id, tier, endpoint_type)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "limit": limit,
                    "window_seconds": RATE_LIMITS[tier][endpoint_type][1],
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        return response


app.add_middleware(RateLimitMiddleware)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/ai/generate")
@rate_limit("ai")
async def generate(request: Request):
    body = await request.json() if request.headers.get("content-length") else {}
    return {"endpoint": "generate", "message": "Request accepted", "input": body}


@app.post("/ai/translate")
@rate_limit("ai")
async def translate(request: Request):
    body = await request.json() if request.headers.get("content-length") else {}
    return {"endpoint": "translate", "message": "Request accepted", "input": body}


@app.get("/data/items")
@rate_limit("read")
async def list_items():
    return {"items": [{"id": 1, "name": "Example item"}]}


@app.get("/data/status")
@rate_limit("read")
async def data_status():
    return {"status": "available"}
