"""Persist preliminary skill gaps on matching results."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_06"
down_revision: str | Sequence[str] | None = "20260801_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "preliminary_matches", sa.Column("preliminary_skill_gaps", sa.JSON(), nullable=False)
    )


def downgrade() -> None:
    op.drop_column("preliminary_matches", "preliminary_skill_gaps")
