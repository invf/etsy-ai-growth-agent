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

RUN_TYPES = (
    "daily",
    "seo_analysis",
    "competitor_analysis",
    "trend_discovery",
    "content_generation",
    "image_analysis",
    "pricing_analysis",
    "audience_discovery",
    "weekly_report",
    "monthly_plan",
    "manual_audit",
)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    run_type: Mapped[str] = mapped_column(String(50))
    triggered_by: Mapped[str] = mapped_column(String(20), default="scheduler")
    status: Mapped[str] = mapped_column(String(20), default="pending")

    # Progress (written by Celery tasks, streamed via SSE)
    progress_pct: Mapped[int] = mapped_column(SmallInteger, default=0)
    current_phase: Mapped[str | None] = mapped_column(String(100))

    # Results
    result_summary: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)

    # Aggregate cost tracking
    total_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)
    credits_used: Mapped[int] = mapped_column(Integer, default=0)
    # held at start, settled on completion
    credits_reserved: Mapped[int] = mapped_column(Integer, default=0)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "run_type IN ('daily','seo_analysis','competitor_analysis',"
            "'trend_discovery','content_generation','image_analysis',"
            "'pricing_analysis','audience_discovery',"
            "'weekly_report','monthly_plan','manual_audit')",
            name="chk_agent_run_type",
        ),
        CheckConstraint(
            "triggered_by IN ('scheduler','user','api')",
            name="chk_agent_run_triggered_by",
        ),
        CheckConstraint(
            "status IN ('pending','running','completed','failed','cancelled')",
            name="chk_agent_run_status",
        ),
        CheckConstraint(
            "progress_pct BETWEEN 0 AND 100",
            name="chk_agent_run_progress",
        ),
    )


class AgentRunLog(Base):
    """Granular per-AI-call cost/token tracking within a run."""

    __tablename__ = "agent_run_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )

    task_name: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(50))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    # Redis response cache hit
    from_cache: Mapped[bool] = mapped_column(Boolean, default=False)
    thinking_used: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
