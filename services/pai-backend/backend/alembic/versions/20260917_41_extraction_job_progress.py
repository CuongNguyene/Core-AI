"""persist worker extraction progress

Revision ID: 20260917_41
Revises: 20260907_40
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260917_41"
down_revision: str | None = "20260907_40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "extraction_jobs",
        sa.Column("stage", sa.String(length=32), nullable=False, server_default="queued"),
    )
    op.add_column("extraction_jobs", sa.Column("completed_units", sa.Integer(), nullable=True))
    op.add_column("extraction_jobs", sa.Column("total_units", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("extraction_jobs", "total_units")
    op.drop_column("extraction_jobs", "completed_units")
    op.drop_column("extraction_jobs", "stage")
