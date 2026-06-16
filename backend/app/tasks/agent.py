"""Daily agent pipeline (ai-agent-spec §4).

Celery Beat fires ``daily_agent_fan_out`` at 07:00 UTC; it queues one
``run_daily_agent`` per eligible store. Each store then runs the chord:

    sync  →  SEO (one analysis per listing, in parallel)  →  synthesis  →  notify

The daily run reserves credits once up front and settles them when the
notify step completes; per-listing SEO analyses inside the run are free
(covered by that single reservation).
"""

import logging
import time
from datetime import datetime, timezone

from celery import chain, chord, group
from celery.canvas import Signature
from sqlalchemy import nulls_first
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.core.config import settings
from app.db.models.agent_run import AgentRun, AgentRunLog
from app.db.models.listing import Listing
from app.db.models.notification import Notification
from app.db.models.seo_analysis import SeoAnalysis
from app.db.models.store import Store
from app.db.models.user import User
from app.db.session import get_db_session
from app.services import email_service
from app.services.credit_service import (
    CREDITS_PER_OPERATION,
    get_credit_service,
)
from app.services.notification_service import check_and_notify_low_credits
from app.services.prompts.daily_synthesizer import synthesize_daily_digest
from app.services.prompts.seo_analyzer import analyze_listing_seo
from app.tasks.seo import _build_seo_row
from app.tasks.sync import sync_store_listings

logger = logging.getLogger(__name__)

DAILY_RUN_COST = CREDITS_PER_OPERATION["daily_agent_run"]
# How many listings one daily run analyzes when the store sets no cap of its own
DEFAULT_LISTING_CAP = 10


def _launch(sig: Signature):
    """Single seam for dispatching a workflow — monkeypatched in tests."""
    return sig.apply_async()


# --------------------------------------------------------------------------- #
# Phase 0: fan out across stores
# --------------------------------------------------------------------------- #
@celery_app.task(name="tasks.agent.daily_agent_fan_out")
def daily_agent_fan_out() -> dict:
    """Beat entrypoint: queue a daily run for every eligible store."""
    with get_db_session() as db:
        stores = (
            db.query(Store)
            .filter_by(agent_enabled=True, status="active")
            .all()
        )
        store_ids = [str(s.id) for s in stores]

    for store_id in store_ids:
        run_daily_agent.delay(store_id)

    logger.info("daily_agent_fan_out queued %d store(s)", len(store_ids))
    return {"status": "ok", "queued": len(store_ids)}


# --------------------------------------------------------------------------- #
# Phase 1: per-store orchestration
# --------------------------------------------------------------------------- #
@celery_app.task(name="tasks.agent.run_daily_agent")
def run_daily_agent(store_id: str) -> dict:
    """Create the daily run, reserve credits, and launch sync → SEO phase."""
    with get_db_session() as db:
        store = db.query(Store).filter_by(id=store_id).first()
        if not store or not store.agent_enabled or store.status != "active":
            return {"status": "skipped", "reason": "store not eligible"}

        user = db.query(User).filter_by(id=store.user_id).first()
        if not user:
            return {"status": "skipped", "reason": "user not found"}

        run = AgentRun(
            store_id=store.id,
            user_id=user.id,
            run_type="daily",
            triggered_by="scheduler",
            status="pending",
            credits_reserved=DAILY_RUN_COST,
        )
        db.add(run)
        db.flush()
        run_id = str(run.id)

        outcome = get_credit_service().reserve(
            str(user.id),
            DAILY_RUN_COST,
            run_id,
            user.credits_balance,
            user.subscription_tier,
        )
        if outcome != "ok":
            run.status = "cancelled"
            run.error_message = f"Credit reservation failed: {outcome}"
            run.completed_at = datetime.now(timezone.utc)
            return {"status": "skipped", "reason": outcome, "run_id": run_id}

    _launch(
        chain(
            sync_store_listings.si(store_id),
            fan_out_seo.si(run_id, store_id),
        )
    )
    return {"status": "queued", "run_id": run_id}


# --------------------------------------------------------------------------- #
# Phase 2: SEO fan-out (chord header) + synthesis/notify (chord callback)
# --------------------------------------------------------------------------- #
@celery_app.task(name="tasks.agent.fan_out_seo", bind=True)
def fan_out_seo(self, run_id: str, store_id: str) -> dict:
    """Pick listings worth analyzing and launch the SEO → synthesis → notify chord."""
    with get_db_session() as db:
        run = db.query(AgentRun).filter_by(id=run_id).first()
        if not run:
            return {"status": "skipped", "reason": "run not found"}

        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        run.current_phase = "seo_analysis"
        run.progress_pct = 20
        db.flush()

        store = db.query(Store).filter_by(id=store_id).first()
        cap = (store.listing_analysis_cap if store else None) or DEFAULT_LISTING_CAP
        listings = (
            db.query(Listing)
            .filter_by(store_id=store_id, state="active")
            .order_by(nulls_first(Listing.seo_scored_at.asc()))
            .limit(cap)
            .all()
        )
        listing_ids = [str(listing.id) for listing in listings]

    finish = chain(
        synthesize_daily.si(run_id, store_id),
        notify_daily_complete.si(run_id),
    )
    if not listing_ids:
        _launch(finish)
    else:
        header = group(analyze_for_daily.si(lid, run_id) for lid in listing_ids)
        _launch(chord(header, finish))

    return {"status": "fanned_out", "run_id": run_id, "listings": len(listing_ids)}


@celery_app.task(name="tasks.agent.analyze_for_daily")
def analyze_for_daily(listing_id: str, run_id: str) -> dict:
    """Analyze one listing's SEO as part of a daily run (no per-listing charge)."""
    started = time.monotonic()
    with get_db_session() as db:
        run = db.query(AgentRun).filter_by(id=run_id).first()
        listing = db.query(Listing).filter_by(id=listing_id).first()
        if not run or not listing:
            return {"status": "skipped", "reason": "run or listing not found"}

        try:
            result, usage = analyze_listing_seo(
                {
                    "title": listing.title,
                    "tags": listing.tags or [],
                    "description": listing.description,
                    "price_usd": listing.price_usd,
                    "views_count": listing.views_count,
                    "favorites_count": listing.favorites_count,
                }
            )
        except Exception as exc:
            # One bad listing must not abort the whole daily run
            logger.warning("daily SEO analysis failed for %s: %s", listing_id, exc)
            return {"status": "failed", "listing_id": listing_id, "error": str(exc)[:200]}

        duration_ms = int((time.monotonic() - started) * 1000)
        db.add(_build_seo_row(listing, run, result, usage))
        db.add(
            AgentRunLog(
                run_id=run.id,
                task_name="seo_analysis",
                model=usage.model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens,
                cost_usd=usage.cost_usd,
                duration_ms=duration_ms,
                thinking_used=False,
            )
        )
        listing.seo_score = result.overall_score
        listing.seo_scored_at = datetime.now(timezone.utc)

        run.total_input_tokens += usage.input_tokens
        run.total_output_tokens += usage.output_tokens
        run.total_cache_read_tokens += usage.cache_read_tokens
        run.total_cost_usd = (run.total_cost_usd or 0) + usage.cost_usd

        return {"status": "ok", "listing_id": listing_id, "score": result.overall_score}


# --------------------------------------------------------------------------- #
# Phase 3: synthesis
# --------------------------------------------------------------------------- #
def _gather_analyses(db: Session, run_id: str) -> list[dict]:
    rows = (
        db.query(SeoAnalysis, Listing.title)
        .join(Listing, SeoAnalysis.listing_id == Listing.id)
        .filter(SeoAnalysis.agent_run_id == run_id)
        .all()
    )
    return [
        {
            "title": title,
            "overall_score": a.overall_score,
            "title_score": a.title_score,
            "tags_score": a.tags_score,
            "description_score": a.description_score,
            "priority": a.priority,
            "issues": (a.title_issues or []) + (a.description_issues or []),
        }
        for a, title in rows
    ]


@celery_app.task(name="tasks.agent.synthesize_daily")
def synthesize_daily(run_id: str, store_id: str) -> dict:
    """Roll the day's per-listing analyses into one store-level digest."""
    started = time.monotonic()
    with get_db_session() as db:
        run = db.query(AgentRun).filter_by(id=run_id).first()
        if not run:
            return {"status": "skipped", "reason": "run not found"}

        run.current_phase = "synthesis"
        run.progress_pct = 80
        db.flush()

        store = db.query(Store).filter_by(id=store_id).first()
        analyses = _gather_analyses(db, run_id)

        if not analyses:
            run.result_summary = {
                "headline": "No listings needed analysis today",
                "summary": "Every active listing already has a recent SEO score.",
                "store_health_score": store.health_score if store else None,
                "analyzed_count": 0,
            }
            return {"status": "ok", "analyzed": 0}

        try:
            digest, usage = synthesize_daily_digest(
                store.shop_name if store else "your shop", analyses
            )
        except Exception as exc:
            logger.warning("daily synthesis failed for run %s: %s", run_id, exc)
            scores = [a["overall_score"] for a in analyses]
            run.result_summary = {
                "headline": f"Analyzed {len(analyses)} listing(s)",
                "summary": "AI synthesis was unavailable; showing raw scores.",
                "store_health_score": round(sum(scores) / len(scores)),
                "analyzed_count": len(analyses),
            }
            return {"status": "degraded", "analyzed": len(analyses)}

        duration_ms = int((time.monotonic() - started) * 1000)
        db.add(
            AgentRunLog(
                run_id=run.id,
                task_name="daily_synthesis",
                model=usage.model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens,
                cost_usd=usage.cost_usd,
                duration_ms=duration_ms,
                thinking_used=True,
            )
        )
        run.total_input_tokens += usage.input_tokens
        run.total_output_tokens += usage.output_tokens
        run.total_cache_read_tokens += usage.cache_read_tokens
        run.total_cost_usd = (run.total_cost_usd or 0) + usage.cost_usd
        run.result_summary = {**digest.model_dump(), "analyzed_count": len(analyses)}

        if store is not None:
            store.health_score = digest.store_health_score
            store.health_computed_at = datetime.now(timezone.utc)

        return {"status": "ok", "analyzed": len(analyses)}


# --------------------------------------------------------------------------- #
# Phase 4: notify + settle
# --------------------------------------------------------------------------- #
@celery_app.task(name="tasks.agent.notify_daily_complete")
def notify_daily_complete(run_id: str) -> dict:
    """Settle credits, post the in-app/email digest, and close out the run."""
    with get_db_session() as db:
        run = db.query(AgentRun).filter_by(id=run_id).first()
        if not run:
            return {"status": "skipped", "reason": "run not found"}

        user = db.query(User).filter_by(id=run.user_id).first()
        store = db.query(Store).filter_by(id=run.store_id).first()
        digest = run.result_summary or {}

        if user is not None:
            try:
                run.credits_used = get_credit_service().settle(run_id, user)
            except Exception:
                pass

        notification = Notification(
            user_id=run.user_id,
            store_id=run.store_id,
            run_id=run.id,
            type="agent_complete",
            priority="medium",
            title=digest.get("headline") or "Your daily SEO review is ready",
            message=digest.get("summary") or "Open your dashboard to see today's recommendations.",
            data={
                "analyzed_count": digest.get("analyzed_count", 0),
                "store_health_score": digest.get("store_health_score"),
            },
            action_url=f"/dashboard/stores/{run.store_id}",
        )
        db.add(notification)

        if user is not None and user.email_notifications:
            sent = email_service.send_email(
                user.email,
                notification.title,
                email_service.daily_digest_email_html(
                    user.name,
                    digest,
                    f"{settings.FRONTEND_URL}/dashboard/stores/{run.store_id}",
                ),
            )
            if sent:
                notification.email_sent = True
                notification.email_sent_at = datetime.now(timezone.utc)

        run.status = "completed"
        run.progress_pct = 100
        run.current_phase = None
        run.completed_at = datetime.now(timezone.utc)
        if run.started_at:
            run.duration_ms = int(
                (run.completed_at - run.started_at).total_seconds() * 1000
            )
        if store is not None:
            store.agent_last_run_at = datetime.now(timezone.utc)

        if user is not None:
            try:
                check_and_notify_low_credits(db, user)
            except Exception:
                pass

        return {"status": "ok", "run_id": run_id, "credits_used": run.credits_used}
