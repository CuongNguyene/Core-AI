"""add SEP-08A authoring brief revisions

Revision ID: 20260907_39
Revises: 20260826_38
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260907_39"
down_revision: str | None = "20260826_38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "course_authoring_requests",
        sa.Column("authoring_workflow_version", sa.String(length=32), nullable=True),
    )
    op.create_table(
        "authoring_brief_revisions",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("clarification", sa.JSON(), nullable=False),
        sa.Column("author_feedback", sa.String(length=4096), nullable=True),
        sa.Column("supersedes_revision_id", sa.String(length=128), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
    )
    op.create_index(
        "ix_authoring_brief_revisions_request_id",
        "authoring_brief_revisions",
        ["request_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_authoring_brief_revisions_request_id", table_name="authoring_brief_revisions")
    op.drop_table("authoring_brief_revisions")
    op.drop_column("course_authoring_requests", "authoring_workflow_version")
