import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SubscriptionPlan(Base):
    """Reference table — seeded plan catalog, not user data."""

    __tablename__ = "subscription_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(20), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    price_monthly_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    price_annual_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    max_stores: Mapped[int] = mapped_column(SmallInteger)  # -1 = unlimited
    credits_monthly: Mapped[int] = mapped_column(Integer)
    credits_rollover_pct: Mapped[int] = mapped_column(SmallInteger, default=0)
    listing_analysis_cap: Mapped[int | None] = mapped_column(SmallInteger)
    features: Mapped[dict] = mapped_column(JSONB)

    # Paddle price IDs (set via admin, not hardcoded)
    paddle_price_id_monthly: Mapped[str | None] = mapped_column(String(100))
    paddle_price_id_annual: Mapped[str | None] = mapped_column(String(100))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "name IN ('trial','starter','growth','pro','agency')",
            name="chk_plan_name",
        ),
    )


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    amount: Mapped[int] = mapped_column(Integer)  # positive = credit
    balance_after: Mapped[int] = mapped_column(Integer)
    transaction_type: Mapped[str] = mapped_column(String(30))

    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL")
    )
    paddle_transaction_id: Mapped[str | None] = mapped_column(String(100))

    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ("
            "'trial_grant','subscription_renewal','topup_purchase',"
            "'agent_run_deduction','manual_adjustment','referral_bonus','refund')",
            name="chk_credit_transaction_type",
        ),
    )


class PaddleEvent(Base):
    """Raw Paddle webhook event log; used for idempotency and debugging."""

    __tablename__ = "paddle_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    paddle_event_id: Mapped[str] = mapped_column(String(100), unique=True)
    event_type: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSONB)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(SmallInteger, default=0)
