"""add capability analysis identity and lifecycle metadata

Revision ID: 20260819_28
Revises: 20260818_27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260819_28"
down_revision: str | None = "20260818_27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "capability_gap_portfolios",
        sa.Column("candidate_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "capability_gap_portfolios",
        sa.Column("analysis_status", sa.String(length=16), nullable=False, server_default="ready"),
    )
    op.add_column(
        "capability_gap_portfolios",
        sa.Column("analysis_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "capability_gap_portfolios",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_capability_gap_portfolios_candidate_id",
        "capability_gap_portfolios",
        ["candidate_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_capability_gap_portfolios_candidate_id",
        table_name="capability_gap_portfolios",
    )
    op.drop_column("capability_gap_portfolios", "idempotency_key")
    op.drop_column("capability_gap_portfolios", "analysis_version")
    op.drop_column("capability_gap_portfolios", "analysis_status")
    op.drop_column("capability_gap_portfolios", "candidate_id")
