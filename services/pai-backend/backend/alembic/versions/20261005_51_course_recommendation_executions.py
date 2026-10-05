"""create immutable recommendation execution snapshots

Revision ID: 20261005_51
Revises: 20260929_50
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261005_51"
down_revision: str | Sequence[str] | None = "20260929_50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "course_recommendation_executions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("request_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("snapshot_schema_version", sa.String(length=16), nullable=False),
        sa.Column("algorithm_id", sa.String(length=128), nullable=False),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("result_kind", sa.String(length=64), nullable=False),
        sa.Column("target_ref", sa.String(length=512), nullable=False),
        sa.Column("source_learning_need_ref", sa.String(length=512), nullable=True),
        sa.Column("organization_ref", sa.Uuid(), nullable=False),
        sa.Column("actor_ref", sa.Uuid(), nullable=False),
        sa.Column("request_snapshot", sa.JSON(), nullable=False),
        sa.Column("result_snapshot", sa.JSON(), nullable=False),
        sa.Column("governance_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_ref",
            "actor_ref",
            "request_key",
            name="uq_course_recommendation_execution_scope_key",
        ),
    )
    op.create_index(
        "ix_course_recommendation_executions_target_ref",
        "course_recommendation_executions",
        ["target_ref"],
    )
    op.create_index(
        "ix_course_recommendation_executions_created_at",
        "course_recommendation_executions",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_course_recommendation_executions_created_at",
        table_name="course_recommendation_executions",
    )
    op.drop_index(
        "ix_course_recommendation_executions_target_ref",
        table_name="course_recommendation_executions",
    )
    op.drop_table("course_recommendation_executions")
