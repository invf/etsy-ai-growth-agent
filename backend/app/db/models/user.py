import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Integer, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True)
    name = Column(String(255))
    password_hash = Column(String(255))
    avatar_url = Column(String)
    timezone = Column(String(100), nullable=False, default="UTC")

    subscription_status = Column(String(20), nullable=False, default="trial")
    subscription_tier = Column(String(20), nullable=False, default="trial")
    billing_interval = Column(String(10), nullable=False, default="monthly")
    trial_ends_at = Column(DateTime(timezone=True))
    subscription_started_at = Column(DateTime(timezone=True))
    subscription_cancelled_at = Column(DateTime(timezone=True))
    subscription_current_period_end = Column(DateTime(timezone=True))

    paddle_customer_id = Column(String(100), unique=True)
    paddle_subscription_id = Column(String(100), unique=True)

    credits_balance = Column(Integer, nullable=False, default=30)
    credits_reserved = Column(Integer, nullable=False, default=0)

    email_notifications = Column(Boolean, nullable=False, default=True)
    email_digest_frequency = Column(String(10), nullable=False, default="daily")
    onboarding_completed = Column(Boolean, nullable=False, default=False)
    onboarding_step = Column(SmallInteger, nullable=False, default=0)

    last_login_at = Column(DateTime(timezone=True))
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    deleted_at = Column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("credits_balance >= 0", name="chk_credits_non_negative"),
        CheckConstraint("credits_reserved >= 0", name="chk_credits_reserved_non_negative"),
        CheckConstraint(
            "subscription_status IN ('trial','active','past_due','cancelling','cancelled','paused')",
            name="chk_subscription_status",
        ),
        CheckConstraint(
            "subscription_tier IN ('trial','starter','growth','pro','agency')",
            name="chk_subscription_tier",
        ),
    )
