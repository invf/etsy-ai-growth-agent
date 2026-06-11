import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String)
    timezone: Mapped[str] = mapped_column(String(100), default="UTC")

    subscription_status: Mapped[str] = mapped_column(String(20), default="trial")
    subscription_tier: Mapped[str] = mapped_column(String(20), default="trial")
    billing_interval: Mapped[str] = mapped_column(String(10), default="monthly")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    subscription_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    subscription_cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    subscription_current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    paddle_customer_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    paddle_subscription_id: Mapped[str | None] = mapped_column(String(100), unique=True)

    credits_balance: Mapped[int] = mapped_column(Integer, default=30)
    credits_reserved: Mapped[int] = mapped_column(Integer, default=0)

    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    email_digest_frequency: Mapped[str] = mapped_column(String(10), default="daily")
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarding_step: Mapped[int] = mapped_column(SmallInteger, default=0)

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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
