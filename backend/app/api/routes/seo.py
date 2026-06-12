import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.agent_run import AgentRun
from app.db.models.listing import Listing
from app.db.models.optimization import ListingOptimization
from app.db.models.seo_analysis import SeoAnalysis
from app.db.models.store import Store
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.seo import SeoApplyIn

router = APIRouter(tags=["seo"])


def _get_owned_listing(listing_id: str, user: User, db: Session) -> Listing:
    listing = db.query(Listing).filter_by(id=listing_id).first()
    if not listing:
        raise HTTPException(
            404, detail={"code": "NOT_FOUND", "message": "Listing not found"}
        )
    store = db.query(Store).filter_by(id=listing.store_id, user_id=user.id).first()
    if not store:
        raise HTTPException(
            403, detail={"code": "FORBIDDEN", "message": "Access denied"}
        )
    return listing


def _analysis_to_dict(analysis: SeoAnalysis) -> dict:
    return {
        "id": str(analysis.id),
        "run_id": str(analysis.agent_run_id) if analysis.agent_run_id else None,
        "overall_score": analysis.overall_score,
        "title_score": analysis.title_score,
        "tags_score": analysis.tags_score,
        "description_score": analysis.description_score,
        "priority": analysis.priority,
        "title_analysis": {
            "current_title": analysis.current_title,
            "optimized_title": analysis.optimized_title,
            "primary_keyword": analysis.title_primary_keyword,
            "keyword_position": analysis.title_keyword_position,
            "issues": analysis.title_issues or [],
            "change_rationale": analysis.title_change_rationale,
        },
        "tags_analysis": {
            "current_tags": analysis.current_tags or [],
            "optimized_tags": analysis.optimized_tags or [],
            "weak_tags": analysis.weak_tags or [],
            "missing_high_value_tags": analysis.missing_high_value_tags or [],
            "replacements": analysis.tag_replacements or [],
        },
        "description_analysis": {
            "issues": analysis.description_issues or [],
            "recommended_additions": analysis.recommended_additions or [],
            "first_paragraph_ok": analysis.first_paragraph_ok,
        },
        "estimated_traffic_lift_pct": analysis.estimated_traffic_lift,
        "competitor_gap_summary": analysis.competitor_gap_summary,
        "from_cache": analysis.from_cache,
        "model_used": analysis.model_used,
        "cost_usd": float(analysis.cost_usd) if analysis.cost_usd else None,
        "created_at": analysis.created_at.isoformat(),
    }


@router.get("/listings/{listing_id}/seo", response_model=dict)
def get_seo_analysis(
    listing_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = _get_owned_listing(listing_id, current_user, db)
    analysis = (
        db.query(SeoAnalysis)
        .filter_by(listing_id=listing.id)
        .order_by(SeoAnalysis.created_at.desc())
        .first()
    )
    if not analysis:
        raise HTTPException(
            404,
            detail={
                "code": "NO_ANALYSIS_FOUND",
                "message": (
                    "No SEO analysis found. "
                    "Trigger one with POST /listings/{id}/seo/analyze"
                ),
            },
        )
    return {"data": _analysis_to_dict(analysis)}


@router.post("/listings/{listing_id}/seo/analyze", response_model=dict, status_code=202)
def trigger_seo_analysis(
    listing_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = _get_owned_listing(listing_id, current_user, db)

    running = (
        db.query(AgentRun)
        .filter(
            AgentRun.store_id == listing.store_id,
            AgentRun.run_type == "seo_analysis",
            AgentRun.status.in_(["pending", "running"]),
        )
        .first()
    )
    if running:
        raise HTTPException(
            409,
            detail={
                "code": "ANALYSIS_IN_PROGRESS",
                "message": "SEO analysis already running for this store",
                "details": {"run_id": str(running.id)},
            },
        )

    # Credit reservation/settlement arrives with CreditService (Day 19)
    run = AgentRun(
        id=uuid.uuid4(),
        store_id=listing.store_id,
        user_id=current_user.id,
        run_type="seo_analysis",
        triggered_by="user",
        status="pending",
    )
    db.add(run)
    db.flush()
    run_id = str(run.id)

    from app.tasks.seo import analyze_single

    analyze_single.apply_async(args=[listing_id, run_id], task_id=run_id)

    return {"data": {"run_id": run_id, "status": "pending", "estimated_seconds": 30}}


@router.post("/listings/{listing_id}/seo/apply", response_model=dict, status_code=201)
def apply_seo_analysis(
    listing_id: str,
    body: SeoApplyIn | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Turn the latest SEO analysis into pending listing_optimizations rows."""
    listing = _get_owned_listing(listing_id, current_user, db)
    analysis = (
        db.query(SeoAnalysis)
        .filter_by(listing_id=listing.id)
        .order_by(SeoAnalysis.created_at.desc())
        .first()
    )
    if not analysis:
        raise HTTPException(
            404,
            detail={
                "code": "NO_ANALYSIS_FOUND",
                "message": "Run analysis first with POST /listings/{id}/seo/analyze",
            },
        )

    fields = body.fields if body else ["title", "tags"]
    # One pending optimization per type per listing; repeat applies are no-ops
    pending_types = {
        opt.optimization_type
        for opt in db.query(ListingOptimization)
        .filter(
            ListingOptimization.listing_id == listing.id,
            ListingOptimization.status == "pending",
        )
        .all()
    }

    created_ids: list[str] = []
    skipped: list[str] = []

    if "title" in fields:
        if "title" in pending_types or not analysis.optimized_title:
            skipped.append("title")
        else:
            opt = ListingOptimization(
                id=uuid.uuid4(),
                listing_id=listing.id,
                agent_run_id=analysis.agent_run_id,
                optimization_type="title",
                old_value=listing.title,
                new_value=analysis.optimized_title,
                change_summary=analysis.title_change_rationale,
                impact_estimate={"seo_score_delta": analysis.title_score},
                status="pending",
            )
            db.add(opt)
            created_ids.append(str(opt.id))

    if "tags" in fields:
        if "tags" in pending_types or not analysis.optimized_tags:
            skipped.append("tags")
        else:
            opt = ListingOptimization(
                id=uuid.uuid4(),
                listing_id=listing.id,
                agent_run_id=analysis.agent_run_id,
                optimization_type="tags",
                old_value=json.dumps(listing.tags or []),
                new_value=json.dumps(analysis.optimized_tags),
                change_summary=(
                    f"Replaced {len(analysis.weak_tags or [])} weak tags, "
                    f"added {len(analysis.missing_high_value_tags or [])} "
                    "high-value tags"
                ),
                impact_estimate={"seo_score_delta": analysis.tags_score},
                status="pending",
            )
            db.add(opt)
            created_ids.append(str(opt.id))

    db.flush()
    return {
        "data": {
            "optimization_ids": created_ids,
            "skipped": skipped,
            "message": (
                f"{len(created_ids)} optimization(s) created. "
                "Review and approve before they are applied to Etsy."
            ),
        }
    }
