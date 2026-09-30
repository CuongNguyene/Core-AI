"""persist rejected lesson validation diagnostics

Revision ID: 20260826_37
Revises: 20260825_36
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260826_37"
down_revision: str | None = "20260825_36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lesson_validation_diagnostics",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("authoring_request_ref", sa.String(length=128), nullable=False),
        sa.Column("plan_ref", sa.String(length=128), nullable=False),
        sa.Column("task_ref", sa.String(length=128), nullable=False),
        sa.Column("lesson_ref", sa.String(length=256), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("generation_run_ref", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("model", sa.String(length=256), nullable=False),
        sa.Column("prompt_version", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("sanitized_parsed_draft", sa.JSON(), nullable=False),
        sa.Column("validation_issues", sa.JSON(), nullable=False),
        sa.Column("section_metrics", sa.JSON(), nullable=False),
        sa.Column("assessment_summary", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_lesson_validation_diagnostics_authoring_request_ref",
        "lesson_validation_diagnostics",
        ["authoring_request_ref"],
    )
    op.create_index(
        "ix_lesson_validation_diagnostics_plan_ref",
        "lesson_validation_diagnostics",
        ["plan_ref"],
    )
    op.create_index(
        "ix_lesson_validation_diagnostics_task_ref",
        "lesson_validation_diagnostics",
        ["task_ref"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lesson_validation_diagnostics_task_ref",
        table_name="lesson_validation_diagnostics",
    )
    op.drop_index(
        "ix_lesson_validation_diagnostics_plan_ref",
        table_name="lesson_validation_diagnostics",
    )
    op.drop_index(
        "ix_lesson_validation_diagnostics_authoring_request_ref",
        table_name="lesson_validation_diagnostics",
    )
    op.drop_table("lesson_validation_diagnostics")
