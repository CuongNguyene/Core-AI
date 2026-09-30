"""add PAI integration learning-result idempotency records

Revision ID: 20260818_25
Revises: 20260811_24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_25"
down_revision: str | None = "20260811_24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_learning_results",
        sa.Column("submission_id", sa.String(length=256), primary_key=True),
        sa.Column("evaluation_reference", sa.String(length=256), nullable=False, unique=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("learner_reference", sa.JSON(), nullable=False),
        sa.Column("course_reference", sa.JSON(), nullable=False),
        sa.Column("activity_reference", sa.JSON(), nullable=False),
        sa.Column("completion_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("integration_learning_results")
