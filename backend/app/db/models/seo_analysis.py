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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SeoAnalysis(Base):
    __tablename__ = "seo_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listings.id", ondelete="CASCADE"), index=True
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL")
    )

    # Scores
    overall_score: Mapped[int] = mapped_column(SmallInteger)
    title_score: Mapped[int | None] = mapped_column(SmallInteger)
    tags_score: Mapped[int | None] = mapped_column(SmallInteger)
    description_score: Mapped[int | None] = mapped_column(SmallInteger)
    priority: Mapped[str] = mapped_column(String(10), default="medium")

    # Title recommendations
    current_title: Mapped[str | None] = mapped_column(Text)
    optimized_title: Mapped[str | None] = mapped_column(Text)
    title_primary_keyword: Mapped[str | None] = mapped_column(String(255))
    title_keyword_position: Mapped[str | None] = mapped_column(String(20))
    title_issues: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    title_change_rationale: Mapped[str | None] = mapped_column(Text)

    # Tag recommendations
    current_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    optimized_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    weak_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    missing_high_value_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    tag_replacements: Mapped[list | None] = mapped_column(JSONB)  # [{remove, add, reason}]

    # Description recommendations
    description_issues: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    recommended_additions: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    first_paragraph_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    optimized_description: Mapped[str | None] = mapped_column(Text)

    # Impact estimates
    estimated_traffic_lift: Mapped[int | None] = mapped_column(SmallInteger)
    competitor_gap_summary: Mapped[str | None] = mapped_column(Text)

    # Full structured output (raw AI response for debugging)
    raw_analysis: Mapped[dict | None] = mapped_column(JSONB)

    # AI metadata
    model_used: Mapped[str | None] = mapped_column(String(100))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    from_cache: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "overall_score BETWEEN 0 AND 100", name="chk_seo_overall_score"
        ),
        CheckConstraint(
            "priority IN ('critical','high','medium','low')",
            name="chk_seo_priority",
        ),
        CheckConstraint(
            "title_keyword_position IN "
            "('first_3_words','first_half','second_half','absent')",
            name="chk_seo_title_keyword_position",
        ),
    )
