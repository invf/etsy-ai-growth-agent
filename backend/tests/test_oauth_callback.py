from fastapi.testclient import TestClient

from app.api.routes import stores
from app.main import app


class FakeRedis:
    def __init__(self, data: dict[str, str] | None = None):
        self.data = data or {}

    def get(self, key):
        return self.data.get(key)

    def delete(self, key):
        self.data.pop(key, None)

    def setex(self, key, ttl, value):
        self.data[key] = value


def test_callback_with_unknown_state_redirects_with_error(monkeypatch):
    monkeypatch.setattr(stores, "get_redis", lambda: FakeRedis())

    client = TestClient(app)
    resp = client.get(
        "/v1/stores/connect/callback",
        params={"code": "x", "state": "unknown-state"},
        follow_redirects=False,
    )
    assert resp.status_code == 307
    assert "error=OAUTH_STATE_MISMATCH" in resp.headers["location"]


def test_callback_failed_token_exchange_redirects_with_error(monkeypatch):
    import json

    fake = FakeRedis(
        {
            "oauth:state:s1": json.dumps(
                {
                    "user_id": "00000000-0000-0000-0000-000000000001",
                    "code_verifier": "v",
                }
            )
        }
    )
    monkeypatch.setattr(stores, "get_redis", lambda: fake)

    def boom(code, verifier):
        raise RuntimeError("etsy down")

    monkeypatch.setattr(stores, "exchange_oauth_code", boom)

    client = TestClient(app)
    resp = client.get(
        "/v1/stores/connect/callback",
        params={"code": "x", "state": "s1"},
        follow_redirects=False,
    )
    assert resp.status_code == 307
    assert "error=OAUTH_FAILED" in resp.headers["location"]
    # state must be single-use even on failure
    assert fake.get("oauth:state:s1") is None
