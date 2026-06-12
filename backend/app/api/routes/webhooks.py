import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.billing import PaddleEvent
from app.db.session import get_db
from app.services.paddle_service import (
    HANDLED_EVENTS,
    PaddleWebhookService,
    verify_paddle_signature,
)

router = APIRouter(tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/webhooks/paddle")
async def paddle_webhook(
    request: Request,
    db: Session = Depends(get_db),
    paddle_signature: str | None = Header(None, alias="Paddle-Signature"),
):
    body = await request.body()

    if not verify_paddle_signature(
        body, paddle_signature, settings.PADDLE_WEBHOOK_SECRET
    ):
        logger.warning("Paddle webhook signature verification failed")
        raise HTTPException(401, detail="Invalid signature")

    payload = json.loads(body)
    event_type = payload.get("event_type")
    event_id = payload.get("notification_id")

    if event_type not in HANDLED_EVENTS:
        return {"status": "ignored", "event_type": event_type}
    if not event_id:
        raise HTTPException(400, detail="Missing notification_id")

    # Idempotency: a successfully processed event is never re-applied
    event = db.query(PaddleEvent).filter_by(paddle_event_id=event_id).first()
    if event and event.error_message is None:
        return {"status": "already_processed"}

    service = PaddleWebhookService(db)
    try:
        user_id = service.handle(event_type, payload.get("data") or {})
    except Exception as exc:
        logger.exception("Paddle webhook handler failed for %s", event_type)
        if event:
            event.retry_count += 1
            event.error_message = str(exc)[:1000]
        else:
            db.add(
                PaddleEvent(
                    paddle_event_id=event_id,
                    event_type=event_type,
                    payload=payload,
                    error_message=str(exc)[:1000],
                )
            )
        # commit now: raising would roll the failure record back
        db.commit()
        raise HTTPException(500, detail="Webhook processing failed")

    if event:  # a previously failed event succeeded on retry
        event.retry_count += 1
        event.error_message = None
        event.user_id = user_id
    else:
        db.add(
            PaddleEvent(
                paddle_event_id=event_id,
                event_type=event_type,
                payload=payload,
                user_id=user_id,
            )
        )
    db.flush()
    return {"status": "ok"}
