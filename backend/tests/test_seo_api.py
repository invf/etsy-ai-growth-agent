import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.db.models.agent_run import AgentRun
from app.db.models.listing import Listing
from app.db.models.seo_analysis import SeoAnalysis
from app.db.models.store import Store
from app.db.session import get_db
from app.main import app


@pytest.fixture
def user():
    return MagicMock(id=uuid.uuid4(), credits_balance=30)


@pytest.fixture
def credits(monkeypatch):
    from app.api.routes import seo as seo_routes

    service = MagicMock()
    service.reserve.return_value = True
    monkeypatch.setattr(seo_routes, "get_credit_service", lambda: service)
    return service


def _client(db, user):
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _db(listing=None, store=None, analysis=None, running=None):
    db = MagicMock()

    def query(model):
        q = MagicMock()
        if model is Listing:
            q.filter_by.return_value.first.return_value = listing
        elif model is Store:
            q.filter_by.return_value.first.return_value = store
        elif model is SeoAnalysis:
            chain = q.filter_by.return_value.order_by.return_value
            chain.first.return_value = analysis
        elif model is AgentRun:
            q.filter.return_value.first.return_value = running
        return q

    db.query.side_effect = query
    return db


def _listing():
    listing = Listing(store_id=uuid.uuid4(), etsy_listing_id=1, title="Mug")
    listing.id = uuid.uuid4()
    return listing


def test_seo_routes_registered():
    paths = {route.path for route in app.routes}
    assert "/v1/listings/{listing_id}/seo" in paths
    assert "/v1/listings/{listing_id}/seo/analyze" in paths


def test_seo_requires_auth():
    resp = TestClient(app).get(f"/v1/listings/{uuid.uuid4()}/seo")
    assert resp.status_code in (401, 403)


def test_get_seo_404_when_listing_missing(user):
    client = _client(_db(listing=None), user)
    resp = client.get(f"/v1/listings/{uuid.uuid4()}/seo")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "NOT_FOUND"


def test_get_seo_403_when_store_not_owned(user):
    client = _client(_db(listing=_listing(), store=None), user)
    resp = client.get(f"/v1/listings/{uuid.uuid4()}/seo")
    assert resp.status_code == 403


def test_get_seo_404_when_no_analysis(user):
    client = _client(_db(listing=_listing(), store=MagicMock(), analysis=None), user)
    resp = client.get(f"/v1/listings/{uuid.uuid4()}/seo")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "NO_ANALYSIS_FOUND"


def test_get_seo_returns_latest_analysis(user):
    listing = _listing()
    analysis = SeoAnalysis(
        listing_id=listing.id,
        overall_score=70,
        title_score=60,
        tags_score=65,
        description_score=80,
        priority="high",
        current_title="Mug",
        optimized_title="Ceramic Mug Handmade",
        title_issues=["too short"],
        current_tags=["mug"],
        optimized_tags=["ceramic mug"],
        estimated_traffic_lift=20,
        competitor_gap_summary="Competitors use seasonal tags.",
        model_used="claude-fable-5",
        from_cache=False,
    )
    analysis.id = uuid.uuid4()
    analysis.created_at = datetime.now(timezone.utc)

    client = _client(_db(listing=listing, store=MagicMock(), analysis=analysis), user)
    resp = client.get(f"/v1/listings/{listing.id}/seo")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["overall_score"] == 70
    assert data["title_analysis"]["optimized_title"] == "Ceramic Mug Handmade"
    assert data["tags_analysis"]["optimized_tags"] == ["ceramic mug"]
    assert data["estimated_traffic_lift_pct"] == 20


def test_trigger_seo_409_when_already_running(user):
    running = MagicMock(id=uuid.uuid4())
    client = _client(
        _db(listing=_listing(), store=MagicMock(), running=running), user
    )
    resp = client.post(f"/v1/listings/{uuid.uuid4()}/seo/analyze")
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "ANALYSIS_IN_PROGRESS"


def test_trigger_seo_402_when_credits_insufficient(user, credits):
    credits.reserve.return_value = False
    credits.available.return_value = 1
    client = _client(_db(listing=_listing(), store=MagicMock(), running=None), user)

    resp = client.post(f"/v1/listings/{uuid.uuid4()}/seo/analyze")

    assert resp.status_code == 402
    detail = resp.json()["detail"]
    assert detail["code"] == "INSUFFICIENT_CREDITS"
    assert detail["details"] == {"required": 2, "available": 1}


def test_trigger_seo_queues_task_and_returns_run_id(user, credits, monkeypatch):
    from app.tasks import seo as seo_mod

    apply_async = MagicMock()
    monkeypatch.setattr(seo_mod.analyze_single, "apply_async", apply_async)

    listing = _listing()
    db = _db(listing=listing, store=MagicMock(), running=None)
    client = _client(db, user)

    resp = client.post(f"/v1/listings/{listing.id}/seo/analyze")

    assert resp.status_code == 202
    data = resp.json()["data"]
    assert data["status"] == "pending"
    assert data["credits_reserved"] == 2
    run_id = data["run_id"]

    # Credits were held atomically for this run
    credits.reserve.assert_called_once_with(str(user.id), 2, run_id, 30)

    # The queued Celery task carries the run id as its task_id
    apply_async.assert_called_once()
    kwargs = apply_async.call_args.kwargs
    assert kwargs["task_id"] == run_id
    assert kwargs["args"] == [str(listing.id), run_id]

    # An AgentRun row was created for this user/store
    run = next(
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], AgentRun)
    )
    assert str(run.id) == run_id
    assert run.run_type == "seo_analysis"
    assert run.triggered_by == "user"
    assert run.store_id == listing.store_id
