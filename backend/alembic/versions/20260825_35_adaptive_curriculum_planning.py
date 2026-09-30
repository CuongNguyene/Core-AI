"""persist adaptive curriculum planning artifacts

Revision ID: 20260825_35
Revises: 20260825_34
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260825_35"
down_revision: str | None = "20260825_34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "course_generation_plans",
        sa.Column("curriculum_plan_ref", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_course_generation_plans_curriculum_plan_ref",
        "course_generation_plans",
        ["curriculum_plan_ref"],
    )
    op.create_table(
        "curriculum_plans",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("authoring_request_ref", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("supersedes_plan_ref", sa.String(length=128), nullable=True),
        sa.Column("course_title", sa.String(length=512), nullable=False),
        sa.Column("course_description", sa.String(length=4096), nullable=False),
        sa.Column("normalized_duration", sa.JSON(), nullable=False),
        sa.Column("learning_objectives", sa.JSON(), nullable=False),
        sa.Column("modules", sa.JSON(), nullable=False),
        sa.Column("estimated_total_learning_hours", sa.Float(), nullable=False),
        sa.Column("planning_metadata", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_curriculum_plans_authoring_request_ref",
        "curriculum_plans",
        ["authoring_request_ref"],
    )
    op.create_index("ix_curriculum_plans_status", "curriculum_plans", ["status"])


def downgrade() -> None:
    op.drop_index("ix_curriculum_plans_status", table_name="curriculum_plans")
    op.drop_index(
        "ix_curriculum_plans_authoring_request_ref",
        table_name="curriculum_plans",
    )
    op.drop_table("curriculum_plans")
    op.drop_index(
        "ix_course_generation_plans_curriculum_plan_ref",
        table_name="course_generation_plans",
    )
    op.drop_column("course_generation_plans", "curriculum_plan_ref")
