"""persist versioned preview capability snapshots

Revision ID: 20260810_21
Revises: 20260807_20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260810_21"
down_revision: str | None = "20260807_20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "capability_gap_portfolios",
        sa.Column(
            "snapshot_schema_version",
            sa.String(length=64),
            nullable=False,
            server_default="capability-gap-v1",
        ),
    )
    op.add_column("capability_gap_portfolios", sa.Column("preview_readiness", sa.JSON()))
    op.add_column(
        "capability_gap_portfolios",
        sa.Column("verification_queue", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("capability_gap_portfolios", "verification_queue")
    op.drop_column("capability_gap_portfolios", "preview_readiness")
    op.drop_column("capability_gap_portfolios", "snapshot_schema_version")
