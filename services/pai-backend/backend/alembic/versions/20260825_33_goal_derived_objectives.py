"""persist goal-driven derived objective provenance

Revision ID: 20260825_33
Revises: 20260824_32
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260825_33"
down_revision: str | None = "20260824_32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "content_generation_results",
        sa.Column("generated_objectives", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.alter_column("content_generation_results", "generated_objectives", server_default=None)


def downgrade() -> None:
    op.drop_column("content_generation_results", "generated_objectives")
