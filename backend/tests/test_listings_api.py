from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.main import app


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id="u1")
    # MagicMock db: any store lookup "succeeds", listing queries are not reached
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_listings_routes_registered():
    paths = {route.path for route in app.routes}
    assert "/v1/stores/{store_id}/listings" in paths
    assert "/v1/stores/{store_id}/listings/{listing_id}" in paths


def test_listings_require_auth():
    resp = TestClient(app).get("/v1/stores/s1/listings")
    assert resp.status_code in (401, 403)


def test_invalid_state_rejected(client):
    resp = client.get("/v1/stores/s1/listings", params={"state": "bogus"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "INVALID_PARAM"


def test_invalid_sort_rejected(client):
    resp = client.get("/v1/stores/s1/listings", params={"sort": "-bogus"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "INVALID_PARAM"


def test_per_page_capped_at_100(client):
    resp = client.get("/v1/stores/s1/listings", params={"per_page": 500})
    assert resp.status_code == 422  # FastAPI Query(le=100) validation
