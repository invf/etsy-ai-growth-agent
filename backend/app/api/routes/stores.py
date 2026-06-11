import json
import secrets

import redis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db.models.store import Store
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.store import OAuthInitiateOut, StoreOut
from app.services.etsy_client import build_etsy_oauth_url

router = APIRouter(prefix="/stores", tags=["stores"])

OAUTH_STATE_TTL_SECONDS = 600
STORE_LIMITS = {"trial": 1, "starter": 1, "growth": 2, "pro": 5, "agency": 20}

_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


def _store_to_out(store: Store) -> StoreOut:
    return StoreOut(
        id=str(store.id),
        etsy_shop_id=store.etsy_shop_id,
        shop_name=store.shop_name,
        shop_url=store.shop_url,
        icon_url=store.icon_url,
        currency_code=store.currency_code,
        status=store.status,
        sync_status=store.sync_status,
        listing_count=store.listing_count,
        health_score=store.health_score,
        health_computed_at=store.health_computed_at,
        agent_enabled=store.agent_enabled,
        agent_last_run_at=store.agent_last_run_at,
        last_synced_at=store.last_synced_at,
        created_at=store.created_at,
    )


@router.get("", response_model=dict)
def list_stores(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stores = db.query(Store).filter_by(user_id=current_user.id).all()
    return {"data": [_store_to_out(s).model_dump(mode="json") for s in stores]}


@router.get("/{store_id}", response_model=dict)
def get_store(
    store_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    store = db.query(Store).filter_by(id=store_id, user_id=current_user.id).first()
    if not store:
        raise HTTPException(
            404, detail={"code": "NOT_FOUND", "message": "Store not found"}
        )
    return {"data": _store_to_out(store).model_dump(mode="json")}


@router.post("/connect/initiate", response_model=dict)
def initiate_etsy_oauth(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    max_stores = STORE_LIMITS.get(current_user.subscription_tier, 1)
    current_count = db.query(Store).filter_by(user_id=current_user.id).count()
    if current_count >= max_stores:
        raise HTTPException(
            403,
            detail={
                "code": "STORE_LIMIT_REACHED",
                "message": (
                    f"Your {current_user.subscription_tier} plan supports "
                    f"{max_stores} store(s)."
                ),
                "details": {"max_stores": max_stores, "upgrade_url": "/billing/upgrade"},
            },
        )

    # PKCE + CSRF state, held in Redis until the callback arrives
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    get_redis().setex(
        f"oauth:state:{state}",
        OAUTH_STATE_TTL_SECONDS,
        json.dumps({"user_id": str(current_user.id), "code_verifier": code_verifier}),
    )

    oauth_url = build_etsy_oauth_url(state, code_verifier)
    return {
        "data": OAuthInitiateOut(
            oauth_url=oauth_url, state=state, expires_in=OAUTH_STATE_TTL_SECONDS
        ).model_dump()
    }
