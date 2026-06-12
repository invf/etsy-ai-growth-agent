from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.notification import Notification
from app.db.models.user import User
from app.db.session import get_db

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _notification_to_dict(n: Notification) -> dict:
    return {
        "id": str(n.id),
        "type": n.type,
        "priority": n.priority,
        "title": n.title,
        "message": n.message,
        "data": n.data,
        "action_url": n.action_url,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat(),
    }


@router.get("", response_model=dict)
def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Notification).filter_by(user_id=current_user.id)
    unread_count = query.filter_by(is_read=False).count()
    if unread_only:
        query = query.filter_by(is_read=False)
    items = query.order_by(Notification.created_at.desc()).limit(limit).all()
    return {
        "data": [_notification_to_dict(n) for n in items],
        "meta": {"unread_count": unread_count},
    }


@router.post("/{notification_id}/read", response_model=dict)
def mark_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notification = (
        db.query(Notification)
        .filter_by(id=notification_id, user_id=current_user.id)
        .first()
    )
    if not notification:
        raise HTTPException(
            404, detail={"code": "NOT_FOUND", "message": "Notification not found"}
        )
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        db.flush()
    return {"data": _notification_to_dict(notification)}
