"""notifications table

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "store_id",
            UUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id", ondelete="SET NULL"),
        ),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("data", JSONB()),
        sa.Column("action_url", sa.Text()),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("email_sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("email_sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "type IN ("
            "'agent_complete','seo_opportunity','trend_alert',"
            "'competitor_change','optimization_ready','optimization_applied',"
            "'billing','low_credits','report_ready','system')",
            name="chk_notification_type",
        ),
        sa.CheckConstraint(
            "priority IN ('low','medium','high')",
            name="chk_notification_priority",
        ),
    )
    op.create_index(
        "idx_notifications_user_unread",
        "notifications",
        ["user_id", "is_read", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_notifications_store",
        "notifications",
        ["store_id"],
        postgresql_where=sa.text("store_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("notifications")
