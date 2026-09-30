"""capability gap portfolio owner and correlation snapshots

Revision ID: 20260806_16
Revises: 20260806_15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260806_16"
down_revision: str | None = "20260806_15"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "capability_gap_portfolios",
        sa.Column("owner_actor_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "capability_gap_portfolios",
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_capability_gap_portfolios_owner_actor_id",
        "capability_gap_portfolios",
        ["owner_actor_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_capability_gap_portfolios_owner_actor_id", table_name="capability_gap_portfolios"
    )
    op.drop_column("capability_gap_portfolios", "correlation_id")
    op.drop_column("capability_gap_portfolios", "owner_actor_id")
