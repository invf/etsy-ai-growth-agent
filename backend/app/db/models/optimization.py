import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ListingOptimization(Base):
    """Human-in-the-loop approval gate for all Etsy write-back operations.

    Created with status='pending'; the user approves or rejects, and an
    approved optimization is then applied to Etsy via the API.
    State machine: pending -> approved/rejected, approved -> applying ->
    applied/failed.
    """

    __tablename__ = "listing_optimizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listings.id", ondelete="CASCADE"), index=True
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL")
    )

    optimization_type: Mapped[str] = mapped_column(String(20))

    # Before / after (JSON string for tags/complex types)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str] = mapped_column(Text)
    change_summary: Mapped[str | None] = mapped_column(Text)
    impact_estimate: Mapped[dict | None] = mapped_column(JSONB)

    # Approval workflow
    status: Mapped[str] = mapped_column(String(20), default="pending")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(50))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    etsy_update_status: Mapped[str | None] = mapped_column(String(10))
    etsy_update_error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "optimization_type IN ('title','description','tags','price','images')",
            name="chk_optimization_type",
        ),
        CheckConstraint(
            "status IN ('pending','approved','rejected','applying','applied','failed')",
            name="chk_optimization_status",
        ),
        CheckConstraint(
            "approved_by IN ('user','auto')",
            name="chk_optimization_approved_by",
        ),
        CheckConstraint(
            "etsy_update_status IN ('pending','success','failed')",
            name="chk_optimization_etsy_update_status",
        ),
    )
