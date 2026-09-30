"""backfill capability gap access scope

Revision ID: 20260806_17
Revises: 20260806_16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260806_17"
down_revision: str | None = "20260806_16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEGACY_SCOPE = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    op.add_column(
        "capability_gap_portfolios",
        sa.Column("organization_id", sa.String(length=36), nullable=True),
    )
    op.execute(
        "UPDATE capability_gap_portfolios "
        f"SET owner_actor_id = '{_LEGACY_SCOPE}' WHERE owner_actor_id IS NULL"
    )
    op.execute(
        "UPDATE capability_gap_portfolios "
        "SET correlation_id = 'legacy-unattributed' WHERE correlation_id IS NULL"
    )
    op.execute(
        "UPDATE capability_gap_portfolios "
        f"SET organization_id = '{_LEGACY_SCOPE}' WHERE organization_id IS NULL"
    )
    op.alter_column("capability_gap_portfolios", "owner_actor_id", nullable=False)
    op.alter_column("capability_gap_portfolios", "correlation_id", nullable=False)
    op.alter_column("capability_gap_portfolios", "organization_id", nullable=False)
    op.create_index(
        "ix_capability_gap_portfolios_organization_id",
        "capability_gap_portfolios",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_capability_gap_portfolios_organization_id",
        table_name="capability_gap_portfolios",
    )
    op.drop_column("capability_gap_portfolios", "organization_id")
    op.alter_column("capability_gap_portfolios", "correlation_id", nullable=True)
    op.alter_column("capability_gap_portfolios", "owner_actor_id", nullable=True)
