import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.db.models.agent_run import AgentRun, AgentRunLog
from app.db.models.listing import Listing
from app.db.models.seo_analysis import SeoAnalysis
from app.db.models.user import User
from app.db.session import get_db_session
from app.schemas.seo import SeoAnalysisResult
from app.services.ai_service import AIRefusalError, AIUsage
from app.services.credit_service import get_credit_service
from app.services.notification_service import check_and_notify_low_credits
from app.services.prompts.seo_analyzer import analyze_listing_seo


def _build_seo_row(
    listing: Listing, run: AgentRun, result: SeoAnalysisResult, usage: AIUsage
) -> SeoAnalysis:
    return SeoAnalysis(
        listing_id=listing.id,
        agent_run_id=run.id,
        overall_score=result.overall_score,
        title_score=result.title_analysis.score,
        tags_score=result.tags_analysis.score,
        description_score=result.description_analysis.score,
        priority=result.priority,
        current_title=listing.title,
        optimized_title=result.title_analysis.optimized_title,
        title_keyword_position=result.title_analysis.primary_keyword_position,
        title_issues=result.title_analysis.issues,
        title_change_rationale=result.title_analysis.title_change_rationale,
        current_tags=listing.tags or [],
        optimized_tags=result.tags_analysis.full_optimized_tag_set,
        weak_tags=result.tags_analysis.weak_tags,
        missing_high_value_tags=result.tags_analysis.missing_high_value_tags,
        tag_replacements=[r.model_dump() for r in result.tags_analysis.replacement_tags],
        description_issues=result.description_analysis.missing_sections,
        recommended_additions=result.description_analysis.recommended_additions,
        first_paragraph_ok=result.description_analysis.first_paragraph_optimized,
        optimized_description=result.description_analysis.optimized_description,
        image_alt_score=result.image_alt_analysis.score,
        image_alt_suggestions=[
            s.model_dump() for s in result.image_alt_analysis.suggestions
        ],
        estimated_traffic_lift=result.estimated_traffic_lift_percent,
        competitor_gap_summary=result.competitor_gap_summary,
        raw_analysis=result.model_dump(),
        model_used=usage.model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=usage.cost_usd,
    )


def _fail_run(db: Session, run: AgentRun, message: str, started: float) -> dict:
    run.status = "failed"
    run.error_message = message[:1000]
    run.completed_at = datetime.now(timezone.utc)
    run.duration_ms = int((time.monotonic() - started) * 1000)
    _release_credits(run)
    return {"status": "failed", "error": message[:200]}


def _release_credits(run: AgentRun) -> None:
    # Best effort: the reservation TTL frees the hold even if Redis is down
    try:
        get_credit_service().release(str(run.user_id), str(run.id))
    except Exception:
        pass


def _settle_credits(db: Session, run: AgentRun) -> None:
    try:
        user = db.query(User).filter_by(id=run.user_id).first()
        if user is not None:
            run.credits_used = get_credit_service().settle(str(run.id), user)
            check_and_notify_low_credits(db, user)
    except Exception:
        pass


@celery_app.task(name="tasks.seo.analyze_single", bind=True)
def analyze_single(self, listing_id: str, run_id: str) -> dict:
    """Run a deep SEO analysis for one listing and persist the result."""
    started = time.monotonic()
    with get_db_session() as db:
        run = db.query(AgentRun).filter_by(id=run_id).first()
        if not run:
            return {"status": "skipped", "reason": "run not found"}

        listing = db.query(Listing).filter_by(id=listing_id).first()
        if not listing:
            return _fail_run(db, run, "Listing not found", started)

        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        run.current_phase = "seo_analysis"
        run.progress_pct = 10
        db.flush()

        try:
            # Competitor/trend context comes from the RAG pipeline (Week 5+);
            # until then the analyzer runs on listing data alone
            result, usage = analyze_listing_seo(
                {
                    "title": listing.title,
                    "tags": listing.tags or [],
                    "description": listing.description,
                    "price_usd": listing.price_usd,
                    "views_count": listing.views_count,
                    "favorites_count": listing.favorites_count,
                    "image_alt_texts": listing.image_alt_texts or [],
                }
            )
        except AIRefusalError as exc:
            return _fail_run(db, run, f"AI refused the request: {exc}", started)
        except Exception as exc:
            return _fail_run(db, run, str(exc), started)

        duration_ms = int((time.monotonic() - started) * 1000)

        analysis = _build_seo_row(listing, run, result, usage)
        db.add(analysis)
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
                thinking_used=True,
            )
        )

        listing.seo_score = result.overall_score
        listing.seo_scored_at = datetime.now(timezone.utc)

        run.total_input_tokens += usage.input_tokens
        run.total_output_tokens += usage.output_tokens
        run.total_cache_read_tokens += usage.cache_read_tokens
        run.total_cost_usd = (run.total_cost_usd or 0) + usage.cost_usd
        run.status = "completed"
        run.progress_pct = 100
        run.current_phase = None
        run.completed_at = datetime.now(timezone.utc)
        run.duration_ms = duration_ms
        run.result_summary = {
            "overall_score": result.overall_score,
            "priority": result.priority,
        }
        _settle_credits(db, run)

        db.flush()
        return {
            "status": "ok",
            "analysis_id": str(analysis.id),
            "overall_score": result.overall_score,
        }
