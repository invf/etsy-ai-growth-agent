"""subscription_plans (+seed), credit_transactions, paddle_events

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PLAN_SEED = [
    # name, display, monthly, annual, stores, credits, rollover, cap, features
    ("trial", "Free Trial", 0.00, 0.00, 1, 30, 0, 20,
     '{"audience": false, "monthly_plan": false, "ab_testing": false, "api_access": false, "white_label": false}'),
    ("starter", "Starter", 19.00, 182.00, 1, 100, 0, 20,
     '{"audience": false, "monthly_plan": false, "ab_testing": false, "api_access": false, "white_label": false}'),
    ("growth", "Growth", 49.00, 470.00, 2, 300, 50, 50,
     '{"audience": true, "monthly_plan": true, "ab_testing": true, "api_access": false, "white_label": false}'),
    ("pro", "Pro", 99.00, 950.00, 5, 750, 50, None,
     '{"audience": true, "monthly_plan": true, "ab_testing": true, "api_access": "read", "white_label": false}'),
    ("agency", "Agency", 299.00, 2870.00, 20, 2500, 100, None,
     '{"audience": true, "monthly_plan": true, "ab_testing": true, "api_access": "read_write", "white_label": true}'),
]


def upgrade() -> None:
    plans = op.create_table(
        "subscription_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(20), nullable=False, unique=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("price_monthly_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("price_annual_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("max_stores", sa.SmallInteger(), nullable=False),
        sa.Column("credits_monthly", sa.Integer(), nullable=False),
        sa.Column("credits_rollover_pct", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("listing_analysis_cap", sa.SmallInteger()),
        sa.Column("features", JSONB(), nullable=False),
        sa.Column("paddle_price_id_monthly", sa.String(100)),
        sa.Column("paddle_price_id_annual", sa.String(100)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "name IN ('trial','starter','growth','pro','agency')",
            name="chk_plan_name",
        ),
    )

    op.bulk_insert(
        plans,
        [
            {
                "name": name,
                "display_name": display_name,
                "price_monthly_usd": monthly,
                "price_annual_usd": annual,
                "max_stores": stores,
                "credits_monthly": credits,
                "credits_rollover_pct": rollover,
                "listing_analysis_cap": cap,
                "features": features,
            }
            for name, display_name, monthly, annual, stores, credits, rollover, cap, features in PLAN_SEED
        ],
    )

    op.create_table(
        "credit_transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("transaction_type", sa.String(30), nullable=False),
        sa.Column(
            "run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id", ondelete="SET NULL"),
        ),
        sa.Column("paddle_transaction_id", sa.String(100)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "transaction_type IN ("
            "'trial_grant','subscription_renewal','topup_purchase',"
            "'agent_run_deduction','manual_adjustment','referral_bonus','refund')",
            name="chk_credit_transaction_type",
        ),
    )
    op.create_index(
        "ix_credit_transactions_user_created",
        "credit_transactions",
        ["user_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "paddle_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("paddle_event_id", sa.String(100), nullable=False, unique=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("error_message", sa.Text()),
        sa.Column("retry_count", sa.SmallInteger(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_paddle_events_type_processed",
        "paddle_events",
        ["event_type", sa.text("processed_at DESC")],
    )


def downgrade() -> None:
    op.drop_table("paddle_events")
    op.drop_table("credit_transactions")
    op.drop_table("subscription_plans")
