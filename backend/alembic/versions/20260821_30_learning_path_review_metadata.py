"""add learning path review and approval metadata

Revision ID: 20260821_30
Revises: 20260820_29
"""

import sqlalchemy as sa

from alembic import op


revision = "20260821_30"
down_revision = "20260820_29"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "learning_paths",
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("learning_paths", sa.Column("reviewed_by", sa.Uuid(), nullable=True))
    op.add_column("learning_paths", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("learning_paths", sa.Column("reviewed_version", sa.Integer(), nullable=True))
    op.add_column("learning_paths", sa.Column("approved_by", sa.Uuid(), nullable=True))
    op.add_column("learning_paths", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("learning_paths", sa.Column("approved_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    for name in (
        "approved_version",
        "approved_at",
        "approved_by",
        "reviewed_version",
        "reviewed_at",
        "reviewed_by",
        "reviewed",
    ):
        op.drop_column("learning_paths", name)
