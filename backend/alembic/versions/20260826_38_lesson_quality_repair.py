"""persist lesson quality repair run metadata

Revision ID: 20260826_38
Revises: 20260826_37
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260826_38"
down_revision: str | None = "20260826_37"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generation_runs",
        sa.Column(
            "generation_mode",
            sa.String(length=16),
            nullable=False,
            server_default="INITIAL",
        ),
    )
    op.add_column(
        "generation_runs",
        sa.Column("repair_source_diagnostic_ref", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generation_runs", "repair_source_diagnostic_ref")
    op.drop_column("generation_runs", "generation_mode")
