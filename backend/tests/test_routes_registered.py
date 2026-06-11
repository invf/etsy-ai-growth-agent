from app.main import app


def test_store_routes_registered():
    paths = {route.path for route in app.routes}
    assert "/v1/stores" in paths
    assert "/v1/stores/{store_id}" in paths
    assert "/v1/stores/connect/initiate" in paths


def test_store_routes_require_auth():
    from fastapi.testclient import TestClient

    client = TestClient(app)
    assert client.get("/v1/stores").status_code in (401, 403)
    assert client.post("/v1/stores/connect/initiate").status_code in (401, 403)
