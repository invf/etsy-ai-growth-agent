"""In-app + email notifications (monetization-spec §2.5).

check_and_notify_low_credits runs after every credit settlement: when
the available balance drops below the tier threshold it creates one
in-app notification and one email per billing cycle (deduplicated via
a Redis flag with a 30-day TTL).
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.notification import Notification
from app.db.models.user import User
from app.services import email_service
from app.services.credit_service import get_credit_service

logger = logging.getLogger(__name__)

LOW_CREDIT_THRESHOLDS = {
    "trial": 10,
    "starter": 20,  # <20 credits = ~4 daily runs remaining
    "growth": 50,
    "pro": 100,
    "agency": 200,
}

NOTIFIED_FLAG_TTL_SECONDS = 30 * 24 * 3600


def _current_billing_cycle() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year}-{now.month:02d}"


def check_and_notify_low_credits(db: Session, user: User) -> Notification | None:
    """Notify once per billing cycle when available credits drop below threshold."""
    threshold = LOW_CREDIT_THRESHOLDS.get(user.subscription_tier, 20)
    credits = get_credit_service()
    available = credits.available(str(user.id), user.credits_balance)
    if available >= threshold:
        return None

    notified_key = f"low_credit_notified:{user.id}:{_current_billing_cycle()}"
    # SET NX doubles as the once-per-cycle guard and is race-safe
    if not credits.redis.set(notified_key, "1", nx=True, ex=NOTIFIED_FLAG_TTL_SECONDS):
        return None

    notification = Notification(
        user_id=user.id,
        type="low_credits",
        priority="high",
        title="You're running low on credits",
        message=(
            f"You have {available} credits left this billing cycle. "
            "Top up or upgrade to keep your daily agent running."
        ),
        data={"available": available, "threshold": threshold},
        action_url="/pricing",
    )
    db.add(notification)

    if user.email_notifications:
        sent = email_service.send_email(
            user.email,
            f"Low credits: {available} remaining",
            email_service.low_credits_email_html(
                user.name, available, f"{settings.FRONTEND_URL}/pricing"
            ),
        )
        if sent:
            notification.email_sent = True
            notification.email_sent_at = datetime.now(timezone.utc)

    logger.info(
        "Low-credit notification for user %s (%s available, threshold %s)",
        user.id,
        available,
        threshold,
    )
    return notification
