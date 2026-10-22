from fastapi.testclient import TestClient
from app.main import app, limiter

client = TestClient(app)


def setup_function():
    # Reset state between tests. In-memory storage is intentional for this assessment.
    with limiter._lock:
        limiter._buckets.clear()


def test_health_is_not_rate_limited():
    for _ in range(8):
        assert client.get("/health").status_code == 200


def test_free_ai_limit_is_five():
    for _ in range(5):
        response = client.post("/ai/generate", headers={"X-User-ID": "free-ai"})
        assert response.status_code == 200
    response = client.post("/ai/generate", headers={"X-User-ID": "free-ai"})
    assert response.status_code == 429
    assert response.json()["error"] == "rate_limit_exceeded"
    assert "Retry-After" in response.headers


def test_free_read_limit_is_thirty():
    for _ in range(30):
        assert client.get("/data/items", headers={"X-User-ID": "free-read"}).status_code == 200
    assert client.get("/data/items", headers={"X-User-ID": "free-read"}).status_code == 429


def test_paid_ai_limit_is_thirty():
    headers = {"X-User-ID": "paid-ai", "X-User-Tier": "paid"}
    for _ in range(30):
        assert client.post("/ai/translate", headers=headers).status_code == 200
    assert client.post("/ai/translate", headers=headers).status_code == 429


def test_paid_read_limit_is_120():
    headers = {"X-User-ID": "paid-read", "X-User-Tier": "paid"}
    for _ in range(120):
        assert client.get("/data/status", headers=headers).status_code == 200
    assert client.get("/data/status", headers=headers).status_code == 429


def test_invalid_tier_defaults_to_free():
    headers = {"X-User-ID": "invalid-tier", "X-User-Tier": "superuser"}
    for _ in range(5):
        assert client.post("/ai/generate", headers=headers).status_code == 200
    assert client.post("/ai/generate", headers=headers).status_code == 429


def test_users_have_independent_buckets():
    for _ in range(5):
        assert client.post("/ai/generate", headers={"X-User-ID": "user-a"}).status_code == 200
    assert client.post("/ai/generate", headers={"X-User-ID": "user-b"}).status_code == 200
