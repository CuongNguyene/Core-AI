"""persist hierarchical course generation plans and lesson tasks

Revision ID: 20260825_34
Revises: 20260825_33
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260825_34"
down_revision: str | None = "20260825_33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generation_runs",
        sa.Column("parent_run_ref", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "generation_runs",
        sa.Column("unit_type", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "generation_runs",
        sa.Column("unit_ref", sa.String(length=256), nullable=True),
    )
    op.create_index(
        "ix_generation_runs_parent_run_ref",
        "generation_runs",
        ["parent_run_ref"],
    )

    op.create_table(
        "course_generation_plans",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("authoring_request_ref", sa.String(length=128), nullable=False),
        sa.Column("parent_run_ref", sa.String(length=128), nullable=False),
        sa.Column("course_title", sa.String(length=512), nullable=False),
        sa.Column("course_description_context", sa.String(length=4096), nullable=False),
        sa.Column("module_plans", sa.JSON(), nullable=False),
        sa.Column("lesson_descriptors", sa.JSON(), nullable=False),
        sa.Column("language", sa.String(length=64), nullable=True),
        sa.Column("duration_constraint", sa.String(length=256), nullable=True),
        sa.Column("prompt_version", sa.String(length=128), nullable=False),
        sa.Column("quality_policy_version", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_course_generation_plans_authoring_request_ref",
        "course_generation_plans",
        ["authoring_request_ref"],
    )
    op.create_index(
        "ix_course_generation_plans_status",
        "course_generation_plans",
        ["status"],
    )

    op.create_table(
        "lesson_generation_tasks",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("plan_ref", sa.String(length=128), nullable=False),
        sa.Column("lesson_ref", sa.String(length=256), nullable=False),
        sa.Column("module_order", sa.Integer(), nullable=False),
        sa.Column("lesson_order", sa.Integer(), nullable=False),
        sa.Column("lesson_title", sa.String(length=512), nullable=False),
        sa.Column("objective_refs", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("latest_run_ref", sa.String(length=128), nullable=True),
        sa.Column("generated_lesson", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_lesson_generation_tasks_plan_ref",
        "lesson_generation_tasks",
        ["plan_ref"],
    )
    op.create_index(
        "ix_lesson_generation_tasks_status",
        "lesson_generation_tasks",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_lesson_generation_tasks_status", table_name="lesson_generation_tasks")
    op.drop_index("ix_lesson_generation_tasks_plan_ref", table_name="lesson_generation_tasks")
    op.drop_table("lesson_generation_tasks")
    op.drop_index("ix_course_generation_plans_status", table_name="course_generation_plans")
    op.drop_index(
        "ix_course_generation_plans_authoring_request_ref",
        table_name="course_generation_plans",
    )
    op.drop_table("course_generation_plans")
    op.drop_index("ix_generation_runs_parent_run_ref", table_name="generation_runs")
    op.drop_column("generation_runs", "unit_ref")
    op.drop_column("generation_runs", "unit_type")
    op.drop_column("generation_runs", "parent_run_ref")
