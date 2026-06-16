import uuid
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.db.models.agent_run import AgentRun
from app.db.models.listing import Listing
from app.db.models.seo_analysis import SeoAnalysis
from app.schemas.seo import SeoAnalysisResult
from app.services.ai_service import AIRefusalError, AIUsage
from app.tasks import seo as seo_mod
from tests.test_seo_analyzer import _valid_payload


def _usage() -> AIUsage:
    return AIUsage(
        model="claude-fable-5",
        input_tokens=1200,
        output_tokens=800,
        cache_read_tokens=2000,
        cache_write_tokens=0,
        cost_usd=Decimal("0.054000"),
    )


def _run() -> AgentRun:
    return AgentRun(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        run_type="seo_analysis",
        status="pending",
        progress_pct=0,
        total_input_tokens=0,
        total_output_tokens=0,
        total_cache_read_tokens=0,
        total_cost_usd=Decimal(0),
    )


def _listing() -> Listing:
    listing = Listing(
        store_id=uuid.uuid4(),
        etsy_listing_id=111,
        title="Handmade mug",
        tags=["mug", "ceramic"],
        views_count=42,
        favorites_count=7,
    )
    listing.id = uuid.uuid4()
    return listing


def _wire_db(monkeypatch, run, listing):
    db = MagicMock()

    def query(model):
        q = MagicMock()
        if model is AgentRun:
            q.filter_by.return_value.first.return_value = run
        elif model is Listing:
            q.filter_by.return_value.first.return_value = listing
        return q

    db.query.side_effect = query

    @contextmanager
    def fake_session():
        yield db

    monkeypatch.setattr(seo_mod, "get_db_session", fake_session)
    return db


@pytest.fixture(autouse=True)
def credits(monkeypatch):
    service = MagicMock()
    service.settle.return_value = 2
    monkeypatch.setattr(seo_mod, "get_credit_service", lambda: service)
    # Unit tests for the task don't exercise the low-credit notify path
    monkeypatch.setattr(seo_mod, "check_and_notify_low_credits", MagicMock())
    return service


@pytest.fixture(autouse=True)
def _no_market(monkeypatch):
    # Keep the analysis tasks off the network: no real Etsy competitor search.
    monkeypatch.setattr(
        seo_mod, "search_active_listings", MagicMock(return_value={"results": []})
    )


def test_gather_market_context_extracts_competitors_and_trending(monkeypatch):
    listing = _listing()  # own tags: mug, ceramic; etsy_listing_id 111
    page = {
        "results": [
            {"listing_id": 111, "title": "Own", "tags": ["mug"]},  # skipped (own)
            {"listing_id": 2, "title": "Rival A", "tags": ["coffee mug", "ceramic"]},
            {"listing_id": 3, "title": "Rival B", "tags": ["coffee mug", "gift"]},
        ]
    }
    monkeypatch.setattr(seo_mod, "search_active_listings", lambda **kw: page)

    competitors, trending = seo_mod._gather_market_context(listing)

    assert [c["title"] for c in competitors] == ["Rival A", "Rival B"]
    # "coffee mug" appears twice and isn't an own tag → top trending;
    # "ceramic" is an own tag → excluded.
    assert trending[0] == "coffee mug"
    assert "ceramic" not in trending


def test_gather_market_context_returns_empty_on_search_failure(monkeypatch):
    def boom(**kw):
        raise RuntimeError("etsy down")

    monkeypatch.setattr(seo_mod, "search_active_listings", boom)
    competitors, trending = seo_mod._gather_market_context(_listing())
    assert competitors == []
    assert trending == []


def test_analyze_single_persists_analysis_and_completes_run(monkeypatch):
    run, listing = _run(), _listing()
    db = _wire_db(monkeypatch, run, listing)
    result = SeoAnalysisResult.model_validate(_valid_payload())
    monkeypatch.setattr(
        seo_mod, "analyze_listing_seo", MagicMock(return_value=(result, _usage()))
    )

    outcome = seo_mod.analyze_single(str(listing.id), str(run.id))

    assert outcome["status"] == "ok"
    assert outcome["overall_score"] == 62

    added = [call.args[0] for call in db.add.call_args_list]
    analysis = next(a for a in added if isinstance(a, SeoAnalysis))
    assert analysis.listing_id == listing.id
    assert analysis.overall_score == 62
    assert analysis.current_title == "Handmade mug"
    assert analysis.optimized_tags == result.tags_analysis.full_optimized_tag_set
    assert analysis.model_used == "claude-fable-5"
    assert analysis.cost_usd == Decimal("0.054000")

    log = next(a for a in added if isinstance(a, seo_mod.AgentRunLog))
    assert log.task_name == "seo_analysis"
    assert log.input_tokens == 1200

    assert listing.seo_score == 62
    assert listing.seo_scored_at is not None

    assert run.status == "completed"
    assert run.progress_pct == 100
    assert run.total_cost_usd == Decimal("0.054000")
    assert run.result_summary == {"overall_score": 62, "priority": "high"}


def test_analyze_single_settles_credits_on_success(monkeypatch, credits):
    run, listing = _run(), _listing()
    _wire_db(monkeypatch, run, listing)
    result = SeoAnalysisResult.model_validate(_valid_payload())
    monkeypatch.setattr(
        seo_mod, "analyze_listing_seo", MagicMock(return_value=(result, _usage()))
    )

    seo_mod.analyze_single(str(listing.id), str(run.id))

    credits.settle.assert_called_once()
    assert credits.settle.call_args.args[0] == str(run.id)
    assert run.credits_used == 2
    credits.release.assert_not_called()


def test_analyze_single_releases_credits_on_failure(monkeypatch, credits):
    run, listing = _run(), _listing()
    _wire_db(monkeypatch, run, listing)
    monkeypatch.setattr(
        seo_mod, "analyze_listing_seo", MagicMock(side_effect=ValueError("boom"))
    )

    seo_mod.analyze_single(str(listing.id), str(run.id))

    credits.release.assert_called_once_with(str(run.user_id), str(run.id))
    credits.settle.assert_not_called()


def test_analyze_single_marks_run_failed_on_error(monkeypatch):
    run, listing = _run(), _listing()
    _wire_db(monkeypatch, run, listing)
    monkeypatch.setattr(
        seo_mod, "analyze_listing_seo", MagicMock(side_effect=ValueError("boom"))
    )

    outcome = seo_mod.analyze_single(str(listing.id), str(run.id))

    assert outcome["status"] == "failed"
    assert run.status == "failed"
    assert "boom" in run.error_message


def test_analyze_single_marks_run_failed_on_refusal(monkeypatch):
    run, listing = _run(), _listing()
    _wire_db(monkeypatch, run, listing)
    monkeypatch.setattr(
        seo_mod,
        "analyze_listing_seo",
        MagicMock(side_effect=AIRefusalError("cyber")),
    )

    outcome = seo_mod.analyze_single(str(listing.id), str(run.id))

    assert outcome["status"] == "failed"
    assert run.status == "failed"
    assert "refused" in run.error_message.lower()


def test_analyze_single_skips_when_run_missing(monkeypatch):
    _wire_db(monkeypatch, run=None, listing=_listing())

    outcome = seo_mod.analyze_single(str(uuid.uuid4()), str(uuid.uuid4()))

    assert outcome == {"status": "skipped", "reason": "run not found"}


def test_analyze_single_fails_run_when_listing_missing(monkeypatch):
    run = _run()
    _wire_db(monkeypatch, run=run, listing=None)

    outcome = seo_mod.analyze_single(str(uuid.uuid4()), str(run.id))

    assert outcome["status"] == "failed"
    assert run.status == "failed"
    assert "Listing not found" in run.error_message
