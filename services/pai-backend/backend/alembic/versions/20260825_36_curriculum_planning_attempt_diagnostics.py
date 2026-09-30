"""persist curriculum planning validation diagnostics

Revision ID: 20260825_36
Revises: 20260825_35
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260825_36"
down_revision: str | None = "20260825_35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "curriculum_planning_attempts",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("authoring_request_ref", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("model", sa.String(length=256), nullable=False),
        sa.Column("prompt_id", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("original_duration_constraint", sa.String(length=256), nullable=True),
        sa.Column("normalized_duration", sa.JSON(), nullable=False),
        sa.Column("weekly_effort_hours", sa.Float(), nullable=True),
        sa.Column("weekly_effort_source", sa.String(length=16), nullable=False),
        sa.Column("estimated_total_learning_hours", sa.Float(), nullable=True),
        sa.Column("min_modules", sa.Integer(), nullable=False),
        sa.Column("max_modules", sa.Integer(), nullable=False),
        sa.Column("min_lessons", sa.Integer(), nullable=False),
        sa.Column("max_lessons", sa.Integer(), nullable=False),
        sa.Column("objective_count", sa.Integer(), nullable=False),
        sa.Column("module_count", sa.Integer(), nullable=False),
        sa.Column("lesson_count", sa.Integer(), nullable=False),
        sa.Column("estimated_candidate_hours", sa.Float(), nullable=True),
        sa.Column("covered_objective_count", sa.Integer(), nullable=False),
        sa.Column("validation_issues", sa.JSON(), nullable=False),
        sa.Column("uncovered_objective_refs", sa.JSON(), nullable=False),
        sa.Column("unknown_objective_refs", sa.JSON(), nullable=False),
        sa.Column("sanitized_parsed_candidate", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_curriculum_planning_attempts_authoring_request_ref",
        "curriculum_planning_attempts",
        ["authoring_request_ref"],
    )
    op.create_index(
        "ix_curriculum_planning_attempts_status",
        "curriculum_planning_attempts",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_curriculum_planning_attempts_status",
        table_name="curriculum_planning_attempts",
    )
    op.drop_index(
        "ix_curriculum_planning_attempts_authoring_request_ref",
        table_name="curriculum_planning_attempts",
    )
    op.drop_table("curriculum_planning_attempts")
