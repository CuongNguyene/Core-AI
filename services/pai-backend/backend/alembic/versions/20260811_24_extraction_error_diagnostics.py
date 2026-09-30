"""persist non-sensitive structured-output diagnostics on extraction jobs

Revision ID: 20260811_24
Revises: 20260810_23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260811_24"
down_revision: str | None = "20260810_23"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("extraction_jobs", sa.Column("error_details", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("extraction_jobs", "error_details")
