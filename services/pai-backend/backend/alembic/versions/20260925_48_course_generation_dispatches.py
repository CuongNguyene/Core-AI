"""add durable course generation dispatch records

Revision ID: 20260925_48
Revises: 20260925_47
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260925_48"
down_revision: str | Sequence[str] | None = "20260925_47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "course_generation_dispatches",
        sa.Column("plan_ref", sa.String(length=128), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("plan_ref"),
    )
    op.create_index(
        "ix_course_generation_dispatches_status", "course_generation_dispatches", ["status"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_course_generation_dispatches_status", table_name="course_generation_dispatches"
    )
    op.drop_table("course_generation_dispatches")
