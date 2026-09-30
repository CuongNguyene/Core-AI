"""persist course generation dispatch execution scope

Revision ID: 20260925_49
Revises: 20260925_48
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260925_49"
down_revision: str | Sequence[str] | None = "20260925_48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "course_generation_dispatches",
        sa.Column("task_statuses", sa.JSON(), nullable=False, server_default='["PENDING"]'),
    )
    op.add_column(
        "course_generation_dispatches",
        sa.Column("assemble_result", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("course_generation_dispatches", "task_statuses", server_default=None)
    op.alter_column("course_generation_dispatches", "assemble_result", server_default=None)


def downgrade() -> None:
    op.drop_column("course_generation_dispatches", "assemble_result")
    op.drop_column("course_generation_dispatches", "task_statuses")
