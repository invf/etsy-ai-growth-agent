import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import cast
from urllib.parse import quote

import httpx
import redis
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.encryption import encrypt
from app.db.models.store import Store
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.store import OAuthInitiateOut, StoreOut
from app.services.etsy_client import (
    OAUTH_SCOPES,
    build_etsy_oauth_url,
    exchange_oauth_code,
    fetch_current_shop,
)

logger = logging.getLogger("etsy.oauth")

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


@router.post("/{store_id}/sync", response_model=dict, status_code=202)
def trigger_store_sync(
    store_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    store = db.query(Store).filter_by(id=store_id, user_id=current_user.id).first()
    if not store:
        raise HTTPException(
            404, detail={"code": "NOT_FOUND", "message": "Store not found"}
        )
    if store.sync_status == "syncing":
        raise HTTPException(
            409,
            detail={"code": "SYNC_IN_PROGRESS", "message": "Sync already running"},
        )
    if not store.etsy_access_token:
        raise HTTPException(
            409,
            detail={
                "code": "STORE_NOT_CONNECTED",
                "message": "Store has no Etsy tokens; reconnect via OAuth",
            },
        )

    from app.tasks.sync import sync_store_listings

    result = sync_store_listings.delay(str(store.id))
    return {"data": {"job_id": result.id, "status": "queued"}}


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


def _error_redirect(code: str) -> RedirectResponse:
    return RedirectResponse(f"{settings.FRONTEND_URL}/dashboard/stores?error={code}")


@router.get("/connect/callback")
def etsy_oauth_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
):
    # CSRF check: state must match what /connect/initiate stored in Redis
    r = get_redis()
    cached = cast(str | None, r.get(f"oauth:state:{state}"))
    if not cached:
        return _error_redirect("OAUTH_STATE_MISMATCH")
    state_data = json.loads(cached)
    r.delete(f"oauth:state:{state}")
    owner_id = uuid.UUID(state_data["user_id"])

    try:
        tokens = exchange_oauth_code(code, state_data["code_verifier"])
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Etsy token exchange failed: %s %s",
            exc.response.status_code,
            exc.response.text,
        )
        return _error_redirect("OAUTH_FAILED")
    except Exception:
        logger.exception("Etsy token exchange raised")
        return _error_redirect("OAUTH_FAILED")

    try:
        shop = fetch_current_shop(tokens["access_token"])
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Etsy fetch shop failed: %s %s",
            exc.response.status_code,
            exc.response.text,
        )
        return _error_redirect("OAUTH_FAILED")
    except Exception:
        logger.exception("Etsy fetch shop raised")
        return _error_redirect("OAUTH_FAILED")

    store = db.query(Store).filter_by(etsy_shop_id=str(shop["shop_id"])).first()
    if not store:
        store = Store(
            user_id=owner_id,
            etsy_shop_id=str(shop["shop_id"]),
            shop_name=shop["shop_name"],
            shop_url=shop.get("url"),
            icon_url=(shop.get("icon") or {}).get("url_fullxfull"),
            currency_code=shop.get("currency_code") or "USD",
            listing_count=shop.get("listing_active_count") or 0,
        )
        db.add(store)
    else:
        # Reconnect: same shop may be re-linked (e.g. after token revocation)
        store.user_id = owner_id
        store.shop_name = shop["shop_name"]
        store.status = "active"

    store.etsy_access_token = encrypt(tokens["access_token"])
    store.etsy_refresh_token = encrypt(tokens["refresh_token"])
    store.token_expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=tokens["expires_in"]
    )
    store.token_scope = OAUTH_SCOPES
    db.flush()

    # Kick off the first listing sync; connection succeeds even if queuing fails
    from app.tasks.sync import sync_store_listings

    try:
        sync_store_listings.delay(str(store.id))
    except Exception:
        pass

    return RedirectResponse(
        f"{settings.FRONTEND_URL}/dashboard/stores"
        f"?connected=true&shop_name={quote(shop['shop_name'])}"
    )
