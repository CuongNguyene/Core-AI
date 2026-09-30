"""persist candidate review idempotency decisions

Revision ID: 20260818_27
Revises: 20260818_26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_27"
down_revision: str | None = "20260818_26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_review_actions",
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("candidates.id"), primary_key=True),
        sa.Column("idempotency_key", sa.String(length=128), primary_key=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("candidate_review_actions")
