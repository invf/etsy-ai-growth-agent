"""add image ALT text capture and SEO image-alt analysis

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "listings",
        sa.Column(
            "image_alt_texts",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "seo_analyses",
        sa.Column("image_alt_score", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "seo_analyses",
        sa.Column("image_alt_suggestions", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("seo_analyses", "image_alt_suggestions")
    op.drop_column("seo_analyses", "image_alt_score")
    op.drop_column("listings", "image_alt_texts")
