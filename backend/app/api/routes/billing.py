from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.billing import SubscriptionPlan
from app.db.models.user import User
from app.db.session import get_db
from app.services.credit_service import get_credit_service

router = APIRouter(prefix="/billing", tags=["billing"])


def _plan_to_dict(plan: SubscriptionPlan) -> dict:
    return {
        "name": plan.name,
        "display_name": plan.display_name,
        "price_monthly_usd": float(plan.price_monthly_usd),
        "price_annual_usd": float(plan.price_annual_usd),
        "max_stores": plan.max_stores,
        "credits_monthly": plan.credits_monthly,
        "credits_rollover_pct": plan.credits_rollover_pct,
        "listing_analysis_cap": plan.listing_analysis_cap,
        "features": plan.features,
        "paddle_price_id_monthly": plan.paddle_price_id_monthly,
        "paddle_price_id_annual": plan.paddle_price_id_annual,
    }


@router.get("/plans", response_model=dict)
def list_plans(db: Session = Depends(get_db)):
    """Public plan catalog for the pricing page (no auth required)."""
    plans = (
        db.query(SubscriptionPlan)
        .filter_by(is_active=True)
        .order_by(SubscriptionPlan.price_monthly_usd.asc())
        .all()
    )
    return {"data": [_plan_to_dict(plan) for plan in plans]}


def _current_plan(db: Session, user: User) -> SubscriptionPlan | None:
    return db.query(SubscriptionPlan).filter_by(name=user.subscription_tier).first()


@router.get("/subscription", response_model=dict)
def get_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = _current_plan(db, current_user)
    price = None
    if plan:
        price = float(
            plan.price_annual_usd
            if current_user.billing_interval == "annual"
            else plan.price_monthly_usd
        )
    return {
        "data": {
            "subscription_status": current_user.subscription_status,
            "subscription_tier": current_user.subscription_tier,
            "billing_interval": current_user.billing_interval,
            "price_usd": price,
            "trial_ends_at": (
                current_user.trial_ends_at.isoformat()
                if current_user.trial_ends_at
                else None
            ),
            "current_period_end": (
                current_user.subscription_current_period_end.isoformat()
                if current_user.subscription_current_period_end
                else None
            ),
            "cancelled_at": (
                current_user.subscription_cancelled_at.isoformat()
                if current_user.subscription_cancelled_at
                else None
            ),
            "paddle_subscription_id": current_user.paddle_subscription_id,
            "paddle_customer_id": current_user.paddle_customer_id,
        }
    }


@router.get("/credits", response_model=dict)
def get_credits(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    credits = get_credit_service()
    reserved = credits.reserved(str(current_user.id))
    available = current_user.credits_balance - reserved
    plan = _current_plan(db, current_user)
    allotment = plan.credits_monthly if plan else 0
    rollover_pct = plan.credits_rollover_pct if plan else 0
    return {
        "data": {
            "balance": current_user.credits_balance,
            "reserved": reserved,
            "available": available,
            "daily_used": credits.daily_used(str(current_user.id)),
            "daily_cap": credits.daily_cap(current_user.subscription_tier),
            "monthly_allotment": allotment,
            "next_renewal_date": (
                current_user.subscription_current_period_end.date().isoformat()
                if current_user.subscription_current_period_end
                else None
            ),
            "rollover_percent": rollover_pct,
            "estimated_balance_at_renewal": (
                int(max(available, 0) * rollover_pct / 100) + allotment
            ),
        }
    }
