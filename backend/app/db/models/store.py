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


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Etsy identifiers
    etsy_shop_id: Mapped[str] = mapped_column(String(100), unique=True)
    shop_name: Mapped[str] = mapped_column(String(255))
    shop_url: Mapped[str | None] = mapped_column(String(500))
    icon_url: Mapped[str | None] = mapped_column(String(500))
    banner_url: Mapped[str | None] = mapped_column(String(500))
    currency_code: Mapped[str] = mapped_column(String(10), default="USD")
    country_code: Mapped[str | None] = mapped_column(String(10))
    listing_count: Mapped[int] = mapped_column(Integer, default=0)
    sale_count: Mapped[int] = mapped_column(Integer, default=0)
    average_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    review_count: Mapped[int] = mapped_column(Integer, default=0)

    # Etsy OAuth tokens (AES-256-GCM encrypted, never stored plaintext)
    etsy_access_token: Mapped[str | None] = mapped_column(Text)
    etsy_refresh_token: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token_scope: Mapped[str | None] = mapped_column(Text)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="active")
    sync_status: Mapped[str] = mapped_column(String(20), default="idle")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_error: Mapped[str | None] = mapped_column(Text)

    # Health scores
    health_score: Mapped[int | None] = mapped_column(SmallInteger)
    health_computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    health_breakdown: Mapped[dict | None] = mapped_column(JSONB)

    # Agent settings
    agent_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    agent_schedule: Mapped[str] = mapped_column(String(50), default="0 7 * * *")
    agent_last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Tier-specific features (FKs added when target tables exist)
    listing_analysis_cap: Mapped[int | None] = mapped_column(SmallInteger)
    brand_voice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    white_label_config_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','paused','disconnected','error')",
            name="chk_store_status",
        ),
        CheckConstraint(
            "sync_status IN ('idle','syncing','error')",
            name="chk_store_sync_status",
        ),
        CheckConstraint(
            "health_score BETWEEN 0 AND 100",
            name="chk_store_health_score",
        ),
    )
