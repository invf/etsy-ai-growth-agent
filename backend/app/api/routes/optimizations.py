import json
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.listing import Listing
from app.db.models.optimization import ListingOptimization
from app.db.models.store import Store
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.seo import OptimizationRejectIn
from app.services.etsy_client import update_listing
from app.services.etsy_token_service import (
    StoreNotConnectedError,
    get_valid_access_token,
)
from app.services.etsy_validation import validate_listing_update
from app.tasks.sync import compute_content_hash

router = APIRouter(tags=["optimizations"])

VALID_STATUSES = {
    "pending",
    "approved",
    "rejected",
    "applying",
    "applied",
    "failed",
    "all",
}


def _value_for_type(optimization_type: str, value: str | None):
    """Tags are stored as JSON strings; decode them for the API payload."""
    if value is None or optimization_type != "tags":
        return value
    try:
        return json.loads(value)
    except ValueError:
        return value


def _optimization_to_dict(opt: ListingOptimization) -> dict:
    return {
        "id": str(opt.id),
        "listing_id": str(opt.listing_id),
        "run_id": str(opt.agent_run_id) if opt.agent_run_id else None,
        "type": opt.optimization_type,
        "old_value": _value_for_type(opt.optimization_type, opt.old_value),
        "new_value": _value_for_type(opt.optimization_type, opt.new_value),
        "change_summary": opt.change_summary,
        "impact_estimate": opt.impact_estimate,
        "status": opt.status,
        "approved_at": opt.approved_at.isoformat() if opt.approved_at else None,
        "approved_by": opt.approved_by,
        "rejected_at": opt.rejected_at.isoformat() if opt.rejected_at else None,
        "rejection_reason": opt.rejection_reason,
        "applied_at": opt.applied_at.isoformat() if opt.applied_at else None,
        "etsy_update_status": opt.etsy_update_status,
        "created_at": opt.created_at.isoformat(),
    }


def _get_owned_optimization(
    optimization_id: str, user: User, db: Session
) -> ListingOptimization:
    opt = (
        db.query(ListingOptimization)
        .join(Listing, Listing.id == ListingOptimization.listing_id)
        .join(Store, Store.id == Listing.store_id)
        .filter(ListingOptimization.id == optimization_id, Store.user_id == user.id)
        .first()
    )
    if not opt:
        raise HTTPException(
            404, detail={"code": "NOT_FOUND", "message": "Optimization not found"}
        )
    return opt


@router.get("/stores/{store_id}/optimizations", response_model=dict)
def list_optimizations(
    store_id: str,
    status: str = Query("pending"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    store = db.query(Store).filter_by(id=store_id, user_id=current_user.id).first()
    if not store:
        raise HTTPException(
            404, detail={"code": "NOT_FOUND", "message": "Store not found"}
        )
    if status not in VALID_STATUSES:
        raise HTTPException(
            422,
            detail={
                "code": "INVALID_PARAM",
                "message": f"status must be one of {sorted(VALID_STATUSES)}",
            },
        )

    query = (
        db.query(ListingOptimization)
        .join(Listing, Listing.id == ListingOptimization.listing_id)
        .filter(Listing.store_id == store.id)
    )
    if status != "all":
        query = query.filter(ListingOptimization.status == status)
    rows = query.order_by(ListingOptimization.created_at.desc()).all()

    return {"data": [_optimization_to_dict(opt) for opt in rows]}


@router.post("/optimizations/{optimization_id}/approve", response_model=dict)
def approve_optimization(
    optimization_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    opt = _get_owned_optimization(optimization_id, current_user, db)
    if opt.status != "pending":
        raise HTTPException(
            409,
            detail={
                "code": "INVALID_STATE",
                "message": f"Only pending optimizations can be approved "
                f"(current status: {opt.status})",
            },
        )

    opt.status = "approved"
    opt.approved_at = datetime.now(timezone.utc)
    opt.approved_by = "user"
    db.flush()
    return {"data": _optimization_to_dict(opt)}


@router.post("/optimizations/{optimization_id}/reject", response_model=dict)
def reject_optimization(
    optimization_id: str,
    body: OptimizationRejectIn | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    opt = _get_owned_optimization(optimization_id, current_user, db)
    if opt.status != "pending":
        raise HTTPException(
            409,
            detail={
                "code": "INVALID_STATE",
                "message": f"Only pending optimizations can be rejected "
                f"(current status: {opt.status})",
            },
        )

    opt.status = "rejected"
    opt.rejected_at = datetime.now(timezone.utc)
    opt.rejection_reason = body.reason if body else None
    db.flush()
    return {"data": _optimization_to_dict(opt)}


def _update_fields(opt: ListingOptimization) -> dict:
    """Map an optimization row to the Etsy updateListing payload."""
    if opt.optimization_type == "tags":
        return {"tags": json.loads(opt.new_value)}
    return {opt.optimization_type: opt.new_value}


def _mark_failed(db: Session, opt: ListingOptimization, error: str) -> None:
    opt.status = "failed"
    opt.etsy_update_status = "failed"
    opt.etsy_update_error = error[:1000]
    # commit now: raising the HTTPException would roll this back otherwise
    db.commit()


@router.post("/optimizations/{optimization_id}/apply", response_model=dict)
def apply_optimization(
    optimization_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The only endpoint that writes to Etsy. Requires status=approved."""
    opt = _get_owned_optimization(optimization_id, current_user, db)
    if opt.status != "approved":
        raise HTTPException(
            409,
            detail={
                "code": "NOT_APPROVED",
                "message": f"Optimization must be approved before applying "
                f"(current status: {opt.status})",
            },
        )

    listing = db.query(Listing).filter_by(id=opt.listing_id).first()
    store = listing and db.query(Store).filter_by(id=listing.store_id).first()
    if not listing or not store:
        raise HTTPException(
            404, detail={"code": "NOT_FOUND", "message": "Listing not found"}
        )

    fields = _update_fields(opt)
    errors = validate_listing_update(fields)
    if errors:
        raise HTTPException(
            422,
            detail={
                "code": "ETSY_VALIDATION_FAILED",
                "message": "Change violates Etsy constraints",
                "details": {"errors": errors},
            },
        )

    opt.status = "applying"
    opt.etsy_update_status = "pending"
    db.flush()

    try:
        token = get_valid_access_token(db, store)
        update_listing(token, store.etsy_shop_id, listing.etsy_listing_id, fields)
    except StoreNotConnectedError:
        _mark_failed(db, opt, "Store has no usable Etsy tokens")
        raise HTTPException(
            409,
            detail={
                "code": "STORE_NOT_CONNECTED",
                "message": "Etsy tokens are invalid; reconnect the store via OAuth",
            },
        )
    except httpx.TimeoutException:
        _mark_failed(db, opt, "Etsy API timeout")
        raise HTTPException(
            503,
            detail={
                "code": "ETSY_UNAVAILABLE",
                "message": "Etsy API timed out; retry later",
            },
        )
    except httpx.HTTPStatusError as exc:
        _mark_failed(
            db, opt, f"Etsy returned {exc.response.status_code}: {exc.response.text}"
        )
        raise HTTPException(
            424,
            detail={
                "code": "ETSY_UPDATE_FAILED",
                "message": "Etsy rejected the update",
                "details": {"etsy_status": exc.response.status_code},
            },
        )

    opt.status = "applied"
    opt.applied_at = datetime.now(timezone.utc)
    opt.etsy_update_status = "success"
    opt.etsy_update_error = None

    # Mirror the change locally so the UI is consistent before the next sync
    if "title" in fields:
        listing.title = fields["title"]
    if "tags" in fields:
        listing.tags = fields["tags"]
    if "description" in fields:
        listing.description = fields["description"]
    listing.content_hash = compute_content_hash(
        listing.title, listing.description, listing.tags or []
    )

    db.flush()
    return {
        "data": {
            "id": str(opt.id),
            "status": opt.status,
            "applied_at": opt.applied_at.isoformat(),
            "etsy_update_status": opt.etsy_update_status,
        }
    }
