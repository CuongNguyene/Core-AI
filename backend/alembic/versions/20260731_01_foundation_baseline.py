"""Create the Alembic foundation baseline.

Revision ID: 20260731_01
Revises:
Create Date: 2026-07-31 00:00:00

"""

from collections.abc import Sequence

revision: str = "20260731_01"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
