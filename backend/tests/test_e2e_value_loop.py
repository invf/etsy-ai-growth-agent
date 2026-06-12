"""Week 3 checkpoint: the full value loop against real handlers.

connect (store w/ encrypted tokens) -> sync (real Etsy field mapping)
-> analyze (real AIService parsing a faked Claude response, credits
reserved+settled) -> review -> approve -> apply (real etsy_client
write-back with faked HTTP).

Only true external boundaries are faked: the Anthropic API, Etsy HTTP,
Redis, and Postgres (in-memory FakeDB running the real query shapes).
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.core.encryption import encrypt
from app.db.models.agent_run import AgentRun, AgentRunLog
from app.db.models.listing import Listing
from app.db.models.optimization import ListingOptimization
from app.db.models.seo_analysis import SeoAnalysis
from app.db.models.store import Store
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.services import etsy_client
from app.services.ai_service import AIService
from app.services.credit_service import CreditService
from app.services.prompts import seo_analyzer
from app.tasks import seo as seo_task
from app.tasks.sync import _apply_etsy_listing, compute_content_hash
from tests.fake_db import FakeDB, FakeRedis
from tests.test_seo_analyzer import _valid_payload

ETSY_ITEM = {
    "listing_id": 777,
    "title": "Handmade ceramic mug",
    "description": "A lovely mug for cozy mornings",
    "tags": ["mug", "ceramic"],
    "price": {"amount": 2999, "divisor": 100, "currency_code": "USD"},
    "state": "active",
    "views": 420,
    "num_favorers": 33,
    "images": [{"url_fullxfull": "https://img/1.jpg"}],
    "original_creation_timestamp": 1700000000,
    "last_modified_timestamp": 1700001000,
}


@pytest.fixture
def world(monkeypatch):
    """Connected store + synced listing + all external boundaries faked."""
    user = User(email="seller@example.com", password_hash="x", credits_balance=30)
    store = Store(
        etsy_shop_id="shop1",
        shop_name="My Shop",
        etsy_access_token=encrypt("etsy-access"),
        etsy_refresh_token=encrypt("etsy-refresh"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    listing = Listing(etsy_listing_id=777)
    _apply_etsy_listing(listing, ETSY_ITEM)  # real sync mapping

    db = FakeDB(user, store, listing)
    store.user_id = user.id
    listing.store_id = store.id

    # One shared DB for routes (dependency) and the Celery task (session factory)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    @contextmanager
    def fake_session():
        yield db

    monkeypatch.setattr(seo_task, "get_db_session", fake_session)

    # Credits: real CreditService on an in-memory Redis
    credits = CreditService(FakeRedis())
    from app.api.routes import seo as seo_routes

    monkeypatch.setattr(seo_routes, "get_credit_service", lambda: credits)
    monkeypatch.setattr(seo_task, "get_credit_service", lambda: credits)

    # Claude: real AIService parsing a canned tool_use response
    ai_response = SimpleNamespace(
        content=[
            SimpleNamespace(
                type="tool_use", name="record_seo_analysis", input=_valid_payload()
            )
        ],
        stop_reason="tool_use",
        stop_details=None,
        usage=SimpleNamespace(
            input_tokens=1500,
            output_tokens=900,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=2000,
        ),
    )
    anthropic_client = MagicMock()
    anthropic_client.messages.create.return_value = ai_response
    monkeypatch.setattr(
        seo_analyzer, "AIService", lambda: AIService(client=anthropic_client)
    )

    # Etsy write-back: fake the HTTP call, keep the real client code
    etsy_response = MagicMock()
    etsy_response.json.return_value = {"listing_id": 777}
    etsy_patch = MagicMock(return_value=etsy_response)
    monkeypatch.setattr(etsy_client, "_throttle", lambda: None)
    monkeypatch.setattr(etsy_client.httpx, "patch", etsy_patch)

    # Celery: capture instead of queueing
    queued: list[tuple] = []
    monkeypatch.setattr(
        seo_task.analyze_single,
        "apply_async",
        lambda args, task_id: queued.append((args, task_id)),
    )

    yield SimpleNamespace(
        user=user,
        store=store,
        listing=listing,
        db=db,
        credits=credits,
        etsy_patch=etsy_patch,
        queued=queued,
        client=TestClient(app),
    )
    app.dependency_overrides.clear()


def test_full_value_loop(world):
    client, listing_id = world.client, str(world.listing.id)

    # --- 1. Trigger the analysis: credits held, run created, task queued
    resp = client.post(f"/v1/listings/{listing_id}/seo/analyze")
    assert resp.status_code == 202
    run_id = resp.json()["data"]["run_id"]
    assert resp.json()["data"]["credits_reserved"] == 2
    assert world.credits.reserved(str(world.user.id)) == 2
    assert world.queued == [([listing_id, run_id], run_id)]

    # --- 2. Worker runs the real task (real AIService parsing)
    outcome = seo_task.analyze_single(listing_id, run_id)
    assert outcome["status"] == "ok"
    assert outcome["overall_score"] == 62

    run = world.db.query(AgentRun).filter_by(id=run_id).first()
    assert run.status == "completed"
    assert run.progress_pct == 100
    assert run.credits_used == 2
    assert run.total_cost_usd > 0
    assert world.user.credits_balance == 28  # settled
    assert world.credits.reserved(str(world.user.id)) == 0
    assert world.listing.seo_score == 62
    assert world.db.query(AgentRunLog).count() == 1

    # --- 3. The browser can read the run + the analysis
    resp = client.get(f"/v1/agent/runs/{run_id}")
    assert resp.json()["data"]["status"] == "completed"

    resp = client.get(f"/v1/listings/{listing_id}/seo")
    assert resp.status_code == 200
    analysis = resp.json()["data"]
    assert analysis["overall_score"] == 62
    optimized_title = analysis["title_analysis"]["optimized_title"]
    assert optimized_title == "Ceramic Coffee Mug Handmade — Cozy Gift"

    # --- 4. Turn the analysis into pending optimizations
    resp = client.post(f"/v1/listings/{listing_id}/seo/apply")
    assert resp.status_code == 201
    optimization_ids = resp.json()["data"]["optimization_ids"]
    assert len(optimization_ids) == 2

    # Repeat click is a no-op (both types already pending)
    resp = client.post(f"/v1/listings/{listing_id}/seo/apply")
    assert resp.json()["data"]["optimization_ids"] == []
    assert sorted(resp.json()["data"]["skipped"]) == ["tags", "title"]

    # --- 5. Approve both
    for opt_id in optimization_ids:
        resp = client.post(f"/v1/optimizations/{opt_id}/approve")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "approved"

    # Applying before approval is impossible by construction; a rejected
    # optimization cannot be approved either (state machine guard)
    resp = client.post(f"/v1/optimizations/{optimization_ids[0]}/approve")
    assert resp.status_code == 409

    # --- 6. Apply both to Etsy (real update_listing, faked HTTP)
    for opt_id in optimization_ids:
        resp = client.post(f"/v1/optimizations/{opt_id}/apply")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "applied"
        assert resp.json()["data"]["etsy_update_status"] == "success"

    assert world.etsy_patch.call_count == 2
    sent = [call.kwargs["data"] for call in world.etsy_patch.call_args_list]
    assert {"title": optimized_title} in sent
    assert {"tags": "ceramic coffee mug,handmade mug gift"} in sent
    for call in world.etsy_patch.call_args_list:
        assert call.args[0].endswith("/application/shops/shop1/listings/777")
        assert call.kwargs["headers"]["Authorization"] == "Bearer etsy-access"

    # --- 7. Local listing mirrors the applied changes
    assert world.listing.title == optimized_title
    assert world.listing.tags == ["ceramic coffee mug", "handmade mug gift"]
    assert world.listing.content_hash == compute_content_hash(
        world.listing.title, world.listing.description, world.listing.tags
    )

    # Every optimization ends in a terminal applied state with an audit trail
    for opt in world.db.query(ListingOptimization).all():
        assert opt.status == "applied"
        assert opt.approved_by == "user"
        assert opt.applied_at is not None

    # The persisted analysis row links back to the run
    stored = world.db.query(SeoAnalysis).first()
    assert str(stored.agent_run_id) == run_id
    assert stored.model_used == "claude-fable-5"


def test_loop_blocks_unapproved_apply(world):
    client, listing_id = world.client, str(world.listing.id)

    client.post(f"/v1/listings/{listing_id}/seo/analyze")
    run_id = world.queued[0][1]
    seo_task.analyze_single(listing_id, run_id)
    resp = client.post(f"/v1/listings/{listing_id}/seo/apply")
    opt_id = resp.json()["data"]["optimization_ids"][0]

    # Straight to apply without approval -> blocked, nothing sent to Etsy
    resp = client.post(f"/v1/optimizations/{opt_id}/apply")
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "NOT_APPROVED"
    world.etsy_patch.assert_not_called()

    # Rejected stays rejected
    resp = client.post(
        f"/v1/optimizations/{opt_id}/reject", json={"reason": "keep mine"}
    )
    assert resp.json()["data"]["status"] == "rejected"
    resp = client.post(f"/v1/optimizations/{opt_id}/apply")
    assert resp.status_code == 409


def test_loop_blocks_when_credits_run_out(world):
    client, listing_id = world.client, str(world.listing.id)
    world.user.credits_balance = 1  # below the 2-credit cost

    resp = client.post(f"/v1/listings/{listing_id}/seo/analyze")

    assert resp.status_code == 402
    assert resp.json()["detail"]["code"] == "INSUFFICIENT_CREDITS"
    assert world.queued == []
    assert world.db.query(AgentRun).count() == 0
