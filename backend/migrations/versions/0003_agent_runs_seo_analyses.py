"""agent_runs, agent_run_logs, seo_analyses

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id",
            UUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_type", sa.String(50), nullable=False),
        sa.Column("triggered_by", sa.String(20), nullable=False, server_default="scheduler"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("progress_pct", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("current_phase", sa.String(100)),
        sa.Column("result_summary", JSONB()),
        sa.Column("error_message", sa.Text()),
        sa.Column("total_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("credits_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credits_reserved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "run_type IN ('daily','seo_analysis','competitor_analysis',"
            "'trend_discovery','content_generation','image_analysis',"
            "'pricing_analysis','audience_discovery',"
            "'weekly_report','monthly_plan','manual_audit')",
            name="chk_agent_run_type",
        ),
        sa.CheckConstraint(
            "triggered_by IN ('scheduler','user','api')",
            name="chk_agent_run_triggered_by",
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','completed','failed','cancelled')",
            name="chk_agent_run_status",
        ),
        sa.CheckConstraint("progress_pct BETWEEN 0 AND 100", name="chk_agent_run_progress"),
    )
    op.create_index("ix_agent_runs_store_id", "agent_runs", ["store_id"])
    op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"])
    op.create_index(
        "ix_agent_runs_store_created", "agent_runs", ["store_id", sa.text("created_at DESC")]
    )

    op.create_table(
        "agent_run_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_name", sa.String(100), nullable=False),
        sa.Column("model", sa.String(50), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("from_cache", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("thinking_used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_agent_run_logs_run_id", "agent_run_logs", ["run_id"])

    op.create_table(
        "seo_analyses",
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
        sa.Column("overall_score", sa.SmallInteger(), nullable=False),
        sa.Column("title_score", sa.SmallInteger()),
        sa.Column("tags_score", sa.SmallInteger()),
        sa.Column("description_score", sa.SmallInteger()),
        sa.Column("priority", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("current_title", sa.Text()),
        sa.Column("optimized_title", sa.Text()),
        sa.Column("title_primary_keyword", sa.String(255)),
        sa.Column("title_keyword_position", sa.String(20)),
        sa.Column("title_issues", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("title_change_rationale", sa.Text()),
        sa.Column("current_tags", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("optimized_tags", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("weak_tags", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("missing_high_value_tags", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("tag_replacements", JSONB()),
        sa.Column("description_issues", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("recommended_additions", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("first_paragraph_ok", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("estimated_traffic_lift", sa.SmallInteger()),
        sa.Column("competitor_gap_summary", sa.Text()),
        sa.Column("raw_analysis", JSONB()),
        sa.Column("model_used", sa.String(100)),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("cost_usd", sa.Numeric(10, 6)),
        sa.Column("from_cache", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("overall_score BETWEEN 0 AND 100", name="chk_seo_overall_score"),
        sa.CheckConstraint(
            "priority IN ('critical','high','medium','low')", name="chk_seo_priority"
        ),
        sa.CheckConstraint(
            "title_keyword_position IN "
            "('first_3_words','first_half','second_half','absent')",
            name="chk_seo_title_keyword_position",
        ),
    )
    op.create_index(
        "ix_seo_analyses_listing_created",
        "seo_analyses",
        ["listing_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_seo_analyses_priority_score", "seo_analyses", ["priority", "overall_score"]
    )


def downgrade() -> None:
    op.drop_table("seo_analyses")
    op.drop_table("agent_run_logs")
    op.drop_table("agent_runs")
