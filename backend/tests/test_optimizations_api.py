import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.api.routes import optimizations as opt_routes
from app.db.models.listing import Listing
from app.db.models.optimization import ListingOptimization
from app.db.models.seo_analysis import SeoAnalysis
from app.db.models.store import Store
from app.db.session import get_db
from app.main import app
from app.services.etsy_token_service import StoreNotConnectedError


@pytest.fixture
def user():
    return MagicMock(id=uuid.uuid4())


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _client(db, user):
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _query_mock(first=None, all_=None):
    q = MagicMock()
    q.join.return_value = q
    q.filter.return_value = q
    q.filter_by.return_value = q
    q.order_by.return_value = q
    q.first.return_value = first
    q.all.return_value = all_ if all_ is not None else []
    return q


def _db(per_model):
    db = MagicMock()
    queries = {model: _query_mock(**cfg) for model, cfg in per_model.items()}
    db.query.side_effect = lambda model, *args: queries.get(model, _query_mock())
    return db


def _listing():
    listing = Listing(
        store_id=uuid.uuid4(), etsy_listing_id=1, title="Mug", tags=["mug"]
    )
    listing.id = uuid.uuid4()
    return listing


def _analysis(listing):
    analysis = SeoAnalysis(
        listing_id=listing.id,
        agent_run_id=uuid.uuid4(),
        overall_score=70,
        title_score=60,
        tags_score=65,
        priority="high",
        optimized_title="Ceramic Mug Handmade",
        title_change_rationale="Front-load keyword",
        optimized_tags=["ceramic mug", "handmade gift"],
        weak_tags=["mug"],
        missing_high_value_tags=["ceramic mug"],
    )
    analysis.id = uuid.uuid4()
    return analysis


def _optimization(status="pending", opt_type="tags"):
    opt = ListingOptimization(
        listing_id=uuid.uuid4(),
        optimization_type=opt_type,
        old_value=json.dumps(["mug"]) if opt_type == "tags" else "Mug",
        new_value=json.dumps(["ceramic mug"]) if opt_type == "tags" else "Better Mug",
        status=status,
    )
    opt.id = uuid.uuid4()
    opt.created_at = datetime.now(timezone.utc)
    return opt


def test_optimization_routes_registered():
    paths = {route.path for route in app.routes}
    assert "/v1/listings/{listing_id}/seo/apply" in paths
    assert "/v1/stores/{store_id}/optimizations" in paths
    assert "/v1/optimizations/{optimization_id}/approve" in paths
    assert "/v1/optimizations/{optimization_id}/reject" in paths


def test_apply_creates_title_and_tags_optimizations(user):
    listing = _listing()
    db = _db(
        {
            Listing: {"first": listing},
            Store: {"first": MagicMock()},
            SeoAnalysis: {"first": _analysis(listing)},
            ListingOptimization: {"all_": []},
        }
    )
    client = _client(db, user)

    resp = client.post(f"/v1/listings/{listing.id}/seo/apply")

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert len(data["optimization_ids"]) == 2
    assert data["skipped"] == []

    added = [
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], ListingOptimization)
    ]
    by_type = {opt.optimization_type: opt for opt in added}
    assert by_type["title"].new_value == "Ceramic Mug Handmade"
    assert by_type["title"].old_value == "Mug"
    assert json.loads(by_type["tags"].new_value) == ["ceramic mug", "handmade gift"]
    assert json.loads(by_type["tags"].old_value) == ["mug"]
    assert all(opt.status == "pending" for opt in added)


def test_apply_skips_types_with_pending_optimization(user):
    listing = _listing()
    db = _db(
        {
            Listing: {"first": listing},
            Store: {"first": MagicMock()},
            SeoAnalysis: {"first": _analysis(listing)},
            ListingOptimization: {"all_": [_optimization(opt_type="title")]},
        }
    )
    client = _client(db, user)

    resp = client.post(f"/v1/listings/{listing.id}/seo/apply")

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert len(data["optimization_ids"]) == 1
    assert data["skipped"] == ["title"]


def test_apply_respects_field_selection(user):
    listing = _listing()
    db = _db(
        {
            Listing: {"first": listing},
            Store: {"first": MagicMock()},
            SeoAnalysis: {"first": _analysis(listing)},
            ListingOptimization: {"all_": []},
        }
    )
    client = _client(db, user)

    resp = client.post(
        f"/v1/listings/{listing.id}/seo/apply", json={"fields": ["title"]}
    )

    assert resp.status_code == 201
    added = [
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], ListingOptimization)
    ]
    assert [opt.optimization_type for opt in added] == ["title"]


def test_apply_404_when_no_analysis(user):
    listing = _listing()
    db = _db(
        {
            Listing: {"first": listing},
            Store: {"first": MagicMock()},
            SeoAnalysis: {"first": None},
        }
    )
    client = _client(db, user)

    resp = client.post(f"/v1/listings/{listing.id}/seo/apply")

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "NO_ANALYSIS_FOUND"


def test_approve_transitions_pending_to_approved(user):
    opt = _optimization(status="pending")
    db = _db({ListingOptimization: {"first": opt}})
    client = _client(db, user)

    resp = client.post(f"/v1/optimizations/{opt.id}/approve")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "approved"
    assert data["approved_by"] == "user"
    assert opt.approved_at is not None
    # Tags values are decoded for the API payload
    assert data["new_value"] == ["ceramic mug"]


def test_approve_409_when_not_pending(user):
    opt = _optimization(status="applied")
    db = _db({ListingOptimization: {"first": opt}})
    client = _client(db, user)

    resp = client.post(f"/v1/optimizations/{opt.id}/approve")

    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "INVALID_STATE"


def test_reject_records_reason(user):
    opt = _optimization(status="pending")
    db = _db({ListingOptimization: {"first": opt}})
    client = _client(db, user)

    resp = client.post(
        f"/v1/optimizations/{opt.id}/reject", json={"reason": "Keep my title"}
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "rejected"
    assert data["rejection_reason"] == "Keep my title"
    assert opt.rejected_at is not None


def test_reject_404_when_not_owned(user):
    db = _db({ListingOptimization: {"first": None}})
    client = _client(db, user)

    resp = client.post(f"/v1/optimizations/{uuid.uuid4()}/reject")

    assert resp.status_code == 404


def test_list_optimizations_404_when_store_not_owned(user):
    db = _db({Store: {"first": None}})
    client = _client(db, user)

    resp = client.get(f"/v1/stores/{uuid.uuid4()}/optimizations")

    assert resp.status_code == 404


def test_list_optimizations_invalid_status_rejected(user):
    db = _db({Store: {"first": MagicMock()}})
    client = _client(db, user)

    resp = client.get(
        f"/v1/stores/{uuid.uuid4()}/optimizations", params={"status": "bogus"}
    )

    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "INVALID_PARAM"


def _apply_setup(monkeypatch, opt, listing=None, update=None, token="tok"):
    """Wire db + service mocks for the apply endpoint."""
    listing = listing or _listing()
    opt.listing_id = listing.id
    store = Store(etsy_shop_id="shop1", shop_name="Shop")
    store.id = listing.store_id
    db = _db(
        {
            ListingOptimization: {"first": opt},
            Listing: {"first": listing},
            Store: {"first": store},
        }
    )
    monkeypatch.setattr(
        opt_routes, "get_valid_access_token", MagicMock(return_value=token)
    )
    monkeypatch.setattr(
        opt_routes, "update_listing", update or MagicMock(return_value={})
    )
    return db, listing, store


def test_apply_optimization_writes_to_etsy_and_updates_listing(user, monkeypatch):
    opt = _optimization(status="approved", opt_type="tags")
    update = MagicMock(return_value={})
    listing = Listing(
        store_id=uuid.uuid4(),
        etsy_listing_id=555,
        title="Mug",
        description="desc",
        tags=["mug"],
    )
    listing.id = uuid.uuid4()
    db, listing, store = _apply_setup(monkeypatch, opt, listing, update)
    client = _client(db, user)

    resp = client.post(f"/v1/optimizations/{opt.id}/apply")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "applied"
    assert data["etsy_update_status"] == "success"

    update.assert_called_once_with("tok", "shop1", 555, {"tags": ["ceramic mug"]})
    assert listing.tags == ["ceramic mug"]
    assert listing.content_hash  # recomputed after local mirror
    assert opt.applied_at is not None


def test_apply_409_when_not_approved(user, monkeypatch):
    opt = _optimization(status="pending")
    db, _, _ = _apply_setup(monkeypatch, opt)
    client = _client(db, user)

    resp = client.post(f"/v1/optimizations/{opt.id}/apply")

    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "NOT_APPROVED"


def test_apply_422_when_etsy_constraints_violated(user, monkeypatch):
    opt = _optimization(status="approved", opt_type="tags")
    opt.new_value = json.dumps(["x" * 21])
    db, _, _ = _apply_setup(monkeypatch, opt)
    client = _client(db, user)

    resp = client.post(f"/v1/optimizations/{opt.id}/apply")

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["code"] == "ETSY_VALIDATION_FAILED"
    assert detail["details"]["errors"]
    # Nothing was sent to Etsy
    opt_routes.update_listing.assert_not_called()


def test_apply_424_when_etsy_rejects(user, monkeypatch):
    request = httpx.Request("PATCH", "https://openapi.etsy.com/x")
    error = httpx.HTTPStatusError(
        "bad", request=request, response=httpx.Response(400, request=request)
    )
    opt = _optimization(status="approved", opt_type="tags")
    db, _, _ = _apply_setup(monkeypatch, opt, update=MagicMock(side_effect=error))
    client = _client(db, user)

    resp = client.post(f"/v1/optimizations/{opt.id}/apply")

    assert resp.status_code == 424
    assert resp.json()["detail"]["code"] == "ETSY_UPDATE_FAILED"
    assert opt.status == "failed"
    assert opt.etsy_update_status == "failed"
    db.commit.assert_called()  # failure state survives the rollback on raise


def test_apply_503_on_etsy_timeout(user, monkeypatch):
    opt = _optimization(status="approved", opt_type="tags")
    db, _, _ = _apply_setup(
        monkeypatch, opt, update=MagicMock(side_effect=httpx.ReadTimeout("slow"))
    )
    client = _client(db, user)

    resp = client.post(f"/v1/optimizations/{opt.id}/apply")

    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "ETSY_UNAVAILABLE"
    assert opt.status == "failed"


def test_apply_409_when_store_disconnected(user, monkeypatch):
    opt = _optimization(status="approved", opt_type="tags")
    db, _, _ = _apply_setup(monkeypatch, opt)
    monkeypatch.setattr(
        opt_routes,
        "get_valid_access_token",
        MagicMock(side_effect=StoreNotConnectedError("gone")),
    )
    client = _client(db, user)

    resp = client.post(f"/v1/optimizations/{opt.id}/apply")

    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "STORE_NOT_CONNECTED"
    assert opt.status == "failed"


def test_list_optimizations_returns_serialized_rows(user):
    opt = _optimization(status="pending")
    db = _db(
        {
            Store: {"first": MagicMock(id=uuid.uuid4())},
            ListingOptimization: {"all_": [opt]},
        }
    )
    client = _client(db, user)

    resp = client.get(f"/v1/stores/{uuid.uuid4()}/optimizations")

    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert len(rows) == 1
    assert rows[0]["type"] == "tags"
    assert rows[0]["old_value"] == ["mug"]
    assert rows[0]["new_value"] == ["ceramic mug"]
