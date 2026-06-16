import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    etsy_listing_id: Mapped[int] = mapped_column(BigInteger, unique=True)

    # Content
    title: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    materials: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    style: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)

    # Pricing
    price_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    original_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    currency_code: Mapped[str] = mapped_column(String(10), default="USD")
    quantity: Mapped[int | None] = mapped_column(Integer)
    is_customizable: Mapped[bool] = mapped_column(Boolean, default=False)

    # State
    state: Mapped[str] = mapped_column(String(20), default="active")

    # Taxonomy / category
    taxonomy_id: Mapped[int | None] = mapped_column(Integer)
    taxonomy_path: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    primary_category: Mapped[str | None] = mapped_column(String(255))
    section_id: Mapped[int | None] = mapped_column(BigInteger)
    section_title: Mapped[str | None] = mapped_column(String(255))

    # Images
    main_image_url: Mapped[str | None] = mapped_column(Text)
    image_urls: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    image_count: Mapped[int] = mapped_column(SmallInteger, default=0)

    # Etsy analytics
    views_count: Mapped[int] = mapped_column(Integer, default=0)
    favorites_count: Mapped[int] = mapped_column(Integer, default=0)
    sales_count: Mapped[int] = mapped_column(Integer, default=0)
    average_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    review_count: Mapped[int] = mapped_column(Integer, default=0)

    # Computed scores (set by analysis tasks)
    seo_score: Mapped[int | None] = mapped_column(SmallInteger)
    seo_scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    image_score: Mapped[int | None] = mapped_column(SmallInteger)
    image_scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Staleness detection for RAG (SHA-256 of title+description+tags)
    content_hash: Mapped[str | None] = mapped_column(String(64))

    # Etsy timestamps
    etsy_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    etsy_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Our timestamps
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
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
            "state IN ('active','inactive','draft','expired','sold_out','removed')",
            name="chk_listing_state",
        ),
        CheckConstraint("seo_score BETWEEN 0 AND 100", name="chk_listing_seo_score"),
        CheckConstraint("image_score BETWEEN 0 AND 100", name="chk_listing_image_score"),
    )


class ListingMetricsHistory(Base):
    """Daily snapshot for trend charts; one row per listing per day."""

    __tablename__ = "listing_metrics_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listings.id", ondelete="CASCADE"), index=True
    )
    views_count: Mapped[int] = mapped_column(Integer, default=0)
    favorites_count: Mapped[int] = mapped_column(Integer, default=0)
    sales_count: Mapped[int] = mapped_column(Integer, default=0)
    price_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    seo_score: Mapped[int | None] = mapped_column(SmallInteger)
    image_score: Mapped[int | None] = mapped_column(SmallInteger)
    recorded_date: Mapped[date] = mapped_column(Date)

    __table_args__ = (
        UniqueConstraint("listing_id", "recorded_date", name="uq_listing_metrics_per_day"),
    )
