"""stores, listings, listing_metrics_history

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("etsy_shop_id", sa.String(100), nullable=False, unique=True),
        sa.Column("shop_name", sa.String(255), nullable=False),
        sa.Column("shop_url", sa.String(500)),
        sa.Column("icon_url", sa.String(500)),
        sa.Column("banner_url", sa.String(500)),
        sa.Column("currency_code", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("country_code", sa.String(10)),
        sa.Column("listing_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sale_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("average_rating", sa.Numeric(3, 2)),
        sa.Column("review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("etsy_access_token", sa.Text()),
        sa.Column("etsy_refresh_token", sa.Text()),
        sa.Column("token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("token_scope", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("sync_status", sa.String(20), nullable=False, server_default="idle"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("sync_error", sa.Text()),
        sa.Column("health_score", sa.SmallInteger()),
        sa.Column("health_computed_at", sa.DateTime(timezone=True)),
        sa.Column("health_breakdown", JSONB()),
        sa.Column("agent_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("agent_schedule", sa.String(50), nullable=False, server_default="0 7 * * *"),
        sa.Column("agent_last_run_at", sa.DateTime(timezone=True)),
        sa.Column("listing_analysis_cap", sa.SmallInteger()),
        sa.Column("brand_voice_id", UUID(as_uuid=True)),
        sa.Column("white_label_config_id", UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('active','paused','disconnected','error')",
            name="chk_store_status",
        ),
        sa.CheckConstraint(
            "sync_status IN ('idle','syncing','error')",
            name="chk_store_sync_status",
        ),
        sa.CheckConstraint("health_score BETWEEN 0 AND 100", name="chk_store_health_score"),
    )
    op.create_index("ix_stores_user_id", "stores", ["user_id"])

    op.create_table(
        "listings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id",
            UUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("etsy_listing_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("title", sa.String(500)),
        sa.Column("description", sa.Text()),
        sa.Column("tags", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("materials", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("style", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("price_usd", sa.Numeric(10, 2)),
        sa.Column("original_price", sa.Numeric(10, 2)),
        sa.Column("currency_code", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("quantity", sa.Integer()),
        sa.Column("is_customizable", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("state", sa.String(20), nullable=False, server_default="active"),
        sa.Column("taxonomy_id", sa.Integer()),
        sa.Column("taxonomy_path", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("primary_category", sa.String(255)),
        sa.Column("section_id", sa.BigInteger()),
        sa.Column("section_title", sa.String(255)),
        sa.Column("main_image_url", sa.Text()),
        sa.Column("image_urls", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("image_count", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("views_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("favorites_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sales_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("average_rating", sa.Numeric(3, 2)),
        sa.Column("review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("seo_score", sa.SmallInteger()),
        sa.Column("seo_scored_at", sa.DateTime(timezone=True)),
        sa.Column("image_score", sa.SmallInteger()),
        sa.Column("image_scored_at", sa.DateTime(timezone=True)),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("etsy_created_at", sa.DateTime(timezone=True)),
        sa.Column("etsy_updated_at", sa.DateTime(timezone=True)),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "state IN ('active','inactive','draft','expired','sold_out','removed')",
            name="chk_listing_state",
        ),
        sa.CheckConstraint("seo_score BETWEEN 0 AND 100", name="chk_listing_seo_score"),
        sa.CheckConstraint("image_score BETWEEN 0 AND 100", name="chk_listing_image_score"),
    )
    op.create_index("ix_listings_store_id", "listings", ["store_id"])

    op.create_table(
        "listing_metrics_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "listing_id",
            UUID(as_uuid=True),
            sa.ForeignKey("listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("views_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("favorites_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sales_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("price_usd", sa.Numeric(10, 2)),
        sa.Column("seo_score", sa.SmallInteger()),
        sa.Column("image_score", sa.SmallInteger()),
        sa.Column("recorded_date", sa.Date(), nullable=False),
        sa.UniqueConstraint("listing_id", "recorded_date", name="uq_listing_metrics_per_day"),
    )
    op.create_index(
        "ix_listing_metrics_history_listing_id", "listing_metrics_history", ["listing_id"]
    )


def downgrade() -> None:
    op.drop_table("listing_metrics_history")
    op.drop_table("listings")
    op.drop_table("stores")
