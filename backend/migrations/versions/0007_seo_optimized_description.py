"""add optimized_description to seo_analyses

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "seo_analyses",
        sa.Column("optimized_description", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("seo_analyses", "optimized_description")
