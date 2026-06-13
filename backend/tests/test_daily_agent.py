import uuid
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import MagicMock

from app.db.models.agent_run import AgentRun, AgentRunLog
from app.db.models.listing import Listing
from app.db.models.notification import Notification
from app.db.models.seo_analysis import SeoAnalysis
from app.db.models.store import Store
from app.db.models.user import User
from app.schemas.agent import DailyDigest
from app.schemas.seo import SeoAnalysisResult
from app.services.ai_service import AIUsage
from app.tasks import agent as agent_mod
from tests.test_seo_analyzer import _valid_payload


def _usage() -> AIUsage:
    return AIUsage(
        model="claude-fable-5",
        input_tokens=1000,
        output_tokens=500,
        cache_read_tokens=2000,
        cache_write_tokens=0,
        cost_usd=Decimal("0.040000"),
    )


def _store(**kw) -> Store:
    store = Store(
        user_id=uuid.uuid4(),
        etsy_shop_id="shop-1",
        shop_name="Test Shop",
        agent_enabled=kw.get("agent_enabled", True),
        status=kw.get("status", "active"),
    )
    store.id = kw.get("id", uuid.uuid4())
    store.listing_analysis_cap = kw.get("cap")
    return store


def _user(**kw) -> User:
    user = User(
        email="seller@example.com",
        name="Seller",
        subscription_tier=kw.get("tier", "starter"),
        credits_balance=kw.get("credits", 100),
        email_notifications=kw.get("email", True),
    )
    user.id = kw.get("id", uuid.uuid4())
    return user


def _run(**kw) -> AgentRun:
    run = AgentRun(
        store_id=kw.get("store_id", uuid.uuid4()),
        user_id=kw.get("user_id", uuid.uuid4()),
        run_type="daily",
        status=kw.get("status", "pending"),
        progress_pct=0,
        credits_reserved=agent_mod.DAILY_RUN_COST,
        total_input_tokens=0,
        total_output_tokens=0,
        total_cache_read_tokens=0,
        total_cost_usd=Decimal(0),
        credits_used=0,
    )
    run.id = kw.get("id", uuid.uuid4())
    run.result_summary = kw.get("result_summary")
    return run


def _listing(**kw) -> Listing:
    listing = Listing(
        store_id=kw.get("store_id", uuid.uuid4()),
        etsy_listing_id=kw.get("etsy_id", 111),
        title=kw.get("title", "Handmade mug"),
        tags=["mug", "ceramic"],
        views_count=42,
        favorites_count=7,
    )
    listing.id = kw.get("id", uuid.uuid4())
    return listing


def _wire(monkeypatch, by_model):
    """Route db.query(Model) (and db.query(Model, extra)) to a configured mock."""
    db = MagicMock()

    def query(*models):
        return by_model.get(models[0], MagicMock())

    db.query.side_effect = query

    @contextmanager
    def fake_session():
        yield db

    monkeypatch.setattr(agent_mod, "get_db_session", fake_session)
    return db


def _scalar_q(value):
    """A query whose .filter_by(...).first() returns value."""
    q = MagicMock()
    q.filter_by.return_value.first.return_value = value
    return q


# --------------------------------------------------------------------------- #
# daily_agent_fan_out
# --------------------------------------------------------------------------- #
def test_fan_out_queues_one_run_per_eligible_store(monkeypatch):
    stores = [_store(), _store()]
    q = MagicMock()
    q.filter_by.return_value.all.return_value = stores
    _wire(monkeypatch, {Store: q})

    delay = MagicMock()
    monkeypatch.setattr(agent_mod.run_daily_agent, "delay", delay)

    outcome = agent_mod.daily_agent_fan_out()

    assert outcome == {"status": "ok", "queued": 2}
    assert delay.call_count == 2
    assert {call.args[0] for call in delay.call_args_list} == {
        str(s.id) for s in stores
    }


# --------------------------------------------------------------------------- #
# run_daily_agent
# --------------------------------------------------------------------------- #
def test_run_daily_agent_creates_run_reserves_and_launches(monkeypatch):
    store = _store()
    user = _user(id=store.user_id)
    db = _wire(monkeypatch, {Store: _scalar_q(store), User: _scalar_q(user)})

    credits = MagicMock()
    credits.reserve.return_value = "ok"
    monkeypatch.setattr(agent_mod, "get_credit_service", lambda: credits)
    launched = MagicMock()
    monkeypatch.setattr(agent_mod, "_launch", launched)

    outcome = agent_mod.run_daily_agent(str(store.id))

    assert outcome["status"] == "queued"
    run = next(c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], AgentRun))
    assert run.run_type == "daily"
    assert run.triggered_by == "scheduler"
    assert run.credits_reserved == agent_mod.DAILY_RUN_COST
    credits.reserve.assert_called_once()
    assert credits.reserve.call_args.args[1] == agent_mod.DAILY_RUN_COST
    launched.assert_called_once()


def test_run_daily_agent_skips_ineligible_store(monkeypatch):
    store = _store(status="disconnected")
    _wire(monkeypatch, {Store: _scalar_q(store)})
    launched = MagicMock()
    monkeypatch.setattr(agent_mod, "_launch", launched)

    outcome = agent_mod.run_daily_agent(str(store.id))

    assert outcome["status"] == "skipped"
    launched.assert_not_called()


def test_run_daily_agent_cancels_run_when_credits_short(monkeypatch):
    store = _store()
    user = _user(id=store.user_id, credits=0)
    db = _wire(monkeypatch, {Store: _scalar_q(store), User: _scalar_q(user)})

    credits = MagicMock()
    credits.reserve.return_value = "insufficient_balance"
    monkeypatch.setattr(agent_mod, "get_credit_service", lambda: credits)
    launched = MagicMock()
    monkeypatch.setattr(agent_mod, "_launch", launched)

    outcome = agent_mod.run_daily_agent(str(store.id))

    assert outcome["status"] == "skipped"
    assert outcome["reason"] == "insufficient_balance"
    run = next(c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], AgentRun))
    assert run.status == "cancelled"
    launched.assert_not_called()


# --------------------------------------------------------------------------- #
# fan_out_seo
# --------------------------------------------------------------------------- #
def test_fan_out_seo_marks_running_and_launches_chord(monkeypatch):
    run = _run()
    store = _store(id=run.store_id)
    listings = [_listing(), _listing()]
    listing_q = MagicMock()
    listing_q.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = (
        listings
    )
    _wire(
        monkeypatch,
        {AgentRun: _scalar_q(run), Store: _scalar_q(store), Listing: listing_q},
    )
    launched = MagicMock()
    monkeypatch.setattr(agent_mod, "_launch", launched)

    outcome = agent_mod.fan_out_seo(str(run.id), str(store.id))

    assert outcome["listings"] == 2
    assert run.status == "running"
    assert run.current_phase == "seo_analysis"
    assert run.started_at is not None
    launched.assert_called_once()


def test_fan_out_seo_with_no_listings_launches_finish_only(monkeypatch):
    run = _run()
    store = _store(id=run.store_id)
    listing_q = MagicMock()
    listing_q.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
    _wire(
        monkeypatch,
        {AgentRun: _scalar_q(run), Store: _scalar_q(store), Listing: listing_q},
    )
    launched = MagicMock()
    monkeypatch.setattr(agent_mod, "_launch", launched)

    outcome = agent_mod.fan_out_seo(str(run.id), str(store.id))

    assert outcome["listings"] == 0
    launched.assert_called_once()


# --------------------------------------------------------------------------- #
# analyze_for_daily
# --------------------------------------------------------------------------- #
def test_analyze_for_daily_persists_analysis_under_run(monkeypatch):
    run, listing = _run(), _listing()
    db = _wire(monkeypatch, {AgentRun: _scalar_q(run), Listing: _scalar_q(listing)})
    result = SeoAnalysisResult.model_validate(_valid_payload())
    monkeypatch.setattr(
        agent_mod, "analyze_listing_seo", MagicMock(return_value=(result, _usage()))
    )

    outcome = agent_mod.analyze_for_daily(str(listing.id), str(run.id))

    assert outcome["status"] == "ok"
    added = [c.args[0] for c in db.add.call_args_list]
    assert any(isinstance(a, SeoAnalysis) for a in added)
    assert any(isinstance(a, AgentRunLog) for a in added)
    assert listing.seo_score == result.overall_score
    assert run.total_cost_usd == Decimal("0.040000")


def test_analyze_for_daily_swallows_one_listing_failure(monkeypatch):
    run, listing = _run(), _listing()
    _wire(monkeypatch, {AgentRun: _scalar_q(run), Listing: _scalar_q(listing)})
    monkeypatch.setattr(
        agent_mod, "analyze_listing_seo", MagicMock(side_effect=ValueError("boom"))
    )

    outcome = agent_mod.analyze_for_daily(str(listing.id), str(run.id))

    assert outcome["status"] == "failed"
    assert "boom" in outcome["error"]


# --------------------------------------------------------------------------- #
# synthesize_daily
# --------------------------------------------------------------------------- #
def _digest() -> DailyDigest:
    return DailyDigest(
        headline="Improve your tag coverage",
        summary="Most listings are leaving tag slots unused.",
        store_health_score=68,
        key_insights=["Tags underused", "Titles solid"],
        top_opportunities=[],
        recommended_actions=["Fill empty tag slots on top 5 listings"],
    )


def test_synthesize_daily_writes_digest_and_store_health(monkeypatch):
    run = _run()
    store = _store(id=run.store_id)
    _wire(monkeypatch, {AgentRun: _scalar_q(run), Store: _scalar_q(store)})

    analyses = [{"title": "Mug", "overall_score": 70, "issues": []}]
    monkeypatch.setattr(agent_mod, "_gather_analyses", lambda db, rid: analyses)
    monkeypatch.setattr(
        agent_mod,
        "synthesize_daily_digest",
        MagicMock(return_value=(_digest(), _usage())),
    )

    outcome = agent_mod.synthesize_daily(str(run.id), str(store.id))

    assert outcome == {"status": "ok", "analyzed": 1}
    assert run.result_summary["headline"] == "Improve your tag coverage"
    assert run.result_summary["analyzed_count"] == 1
    assert store.health_score == 68
    assert store.health_computed_at is not None


def test_synthesize_daily_no_analyses_skips_ai(monkeypatch):
    run = _run()
    store = _store(id=run.store_id)
    _wire(monkeypatch, {AgentRun: _scalar_q(run), Store: _scalar_q(store)})
    monkeypatch.setattr(agent_mod, "_gather_analyses", lambda db, rid: [])
    ai = MagicMock()
    monkeypatch.setattr(agent_mod, "synthesize_daily_digest", ai)

    outcome = agent_mod.synthesize_daily(str(run.id), str(store.id))

    assert outcome == {"status": "ok", "analyzed": 0}
    assert run.result_summary["analyzed_count"] == 0
    ai.assert_not_called()


def test_synthesize_daily_degrades_when_ai_fails(monkeypatch):
    run = _run()
    store = _store(id=run.store_id)
    _wire(monkeypatch, {AgentRun: _scalar_q(run), Store: _scalar_q(store)})
    monkeypatch.setattr(
        agent_mod,
        "_gather_analyses",
        lambda db, rid: [
            {"title": "A", "overall_score": 60, "issues": []},
            {"title": "B", "overall_score": 80, "issues": []},
        ],
    )
    monkeypatch.setattr(
        agent_mod,
        "synthesize_daily_digest",
        MagicMock(side_effect=RuntimeError("api down")),
    )

    outcome = agent_mod.synthesize_daily(str(run.id), str(store.id))

    assert outcome["status"] == "degraded"
    assert run.result_summary["store_health_score"] == 70  # mean of 60, 80


# --------------------------------------------------------------------------- #
# notify_daily_complete
# --------------------------------------------------------------------------- #
def test_notify_daily_complete_settles_and_completes(monkeypatch):
    user = _user()
    run = _run(user_id=user.id, result_summary={"headline": "Done", "summary": "ok"})
    store = _store(id=run.store_id)
    db = _wire(
        monkeypatch,
        {AgentRun: _scalar_q(run), User: _scalar_q(user), Store: _scalar_q(store)},
    )

    credits = MagicMock()
    credits.settle.return_value = 5
    monkeypatch.setattr(agent_mod, "get_credit_service", lambda: credits)
    monkeypatch.setattr(agent_mod, "check_and_notify_low_credits", MagicMock())
    monkeypatch.setattr(agent_mod.email_service, "send_email", MagicMock(return_value=True))

    outcome = agent_mod.notify_daily_complete(str(run.id))

    assert outcome["status"] == "ok"
    assert run.status == "completed"
    assert run.progress_pct == 100
    assert run.credits_used == 5
    credits.settle.assert_called_once_with(str(run.id), user)
    notif = next(
        c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], Notification)
    )
    assert notif.type == "agent_complete"
    assert notif.title == "Done"
    assert store.agent_last_run_at is not None
