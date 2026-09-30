"""Store normalized role requirement rules with role profiles.

Revision ID: 20260801_05
Revises: 20260731_04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260801_05"
down_revision: str | Sequence[str] | None = "20260731_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("role_competency_profiles", sa.Column("requirements", sa.JSON(), nullable=False))


def downgrade() -> None:
    op.drop_column("role_competency_profiles", "requirements")
