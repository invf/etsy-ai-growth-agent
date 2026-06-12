"""listing_optimizations

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "listing_optimizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "listing_id",
            UUID(as_uuid=True),
            sa.ForeignKey("listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id", ondelete="SET NULL"),
        ),
        sa.Column("optimization_type", sa.String(20), nullable=False),
        sa.Column("old_value", sa.Text()),
        sa.Column("new_value", sa.Text(), nullable=False),
        sa.Column("change_summary", sa.Text()),
        sa.Column("impact_estimate", JSONB()),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("approved_by", sa.String(50)),
        sa.Column("rejected_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("etsy_update_status", sa.String(10)),
        sa.Column("etsy_update_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "optimization_type IN ('title','description','tags','price','images')",
            name="chk_optimization_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected','applying','applied','failed')",
            name="chk_optimization_status",
        ),
        sa.CheckConstraint(
            "approved_by IN ('user','auto')",
            name="chk_optimization_approved_by",
        ),
        sa.CheckConstraint(
            "etsy_update_status IN ('pending','success','failed')",
            name="chk_optimization_etsy_update_status",
        ),
    )
    op.create_index(
        "ix_listing_optimizations_listing_status",
        "listing_optimizations",
        ["listing_id", "status"],
    )
    op.create_index(
        "ix_listing_optimizations_status_created",
        "listing_optimizations",
        ["status", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_table("listing_optimizations")
