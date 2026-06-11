"""users, sessions, password_reset_tokens, oauth_accounts

Revision ID: 0001
Revises:
Create Date: 2026-06-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255)),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("avatar_url", sa.String()),
        sa.Column("timezone", sa.String(100), nullable=False, server_default="UTC"),
        sa.Column("subscription_status", sa.String(20), nullable=False, server_default="trial"),
        sa.Column("subscription_tier", sa.String(20), nullable=False, server_default="trial"),
        sa.Column("billing_interval", sa.String(10), nullable=False, server_default="monthly"),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True)),
        sa.Column("subscription_started_at", sa.DateTime(timezone=True)),
        sa.Column("subscription_cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("subscription_current_period_end", sa.DateTime(timezone=True)),
        sa.Column("paddle_customer_id", sa.String(100), unique=True),
        sa.Column("paddle_subscription_id", sa.String(100), unique=True),
        sa.Column("credits_balance", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("credits_reserved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("email_notifications", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("email_digest_frequency", sa.String(10), nullable=False, server_default="daily"),
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("onboarding_step", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("credits_balance >= 0", name="chk_credits_non_negative"),
        sa.CheckConstraint("credits_reserved >= 0", name="chk_credits_reserved_non_negative"),
        sa.CheckConstraint(
            "subscription_status IN ('trial','active','past_due','cancelling','cancelled','paused')",
            name="chk_subscription_status",
        ),
        sa.CheckConstraint(
            "subscription_tier IN ('trial','starter','growth','pro','agency')",
            name="chk_subscription_tier",
        ),
    )

    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("user_agent", sa.String()),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])

    op.create_table(
        "oauth_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_account_id", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("provider", "provider_account_id", name="uq_oauth_provider_account"),
    )
    op.create_index("ix_oauth_accounts_user_id", "oauth_accounts", ["user_id"])


def downgrade() -> None:
    op.drop_table("oauth_accounts")
    op.drop_table("password_reset_tokens")
    op.drop_table("sessions")
    op.drop_table("users")
