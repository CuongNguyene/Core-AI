"""persist course-authoring requests and generated course drafts

Revision ID: 20260824_32
Revises: 20260821_31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260824_32"
down_revision: str | None = "20260821_31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "course_authoring_requests",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("training_brief", sa.JSON(), nullable=False),
        sa.Column("audience_snapshot", sa.JSON(), nullable=False),
        sa.Column("learning_need_refs", sa.JSON(), nullable=False),
        sa.Column("objective_refs", sa.JSON(), nullable=False),
        sa.Column("instructional_blueprint_ref", sa.String(length=256), nullable=True),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by_actor_ref", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_course_authoring_requests_created_by_actor_ref",
        "course_authoring_requests",
        ["created_by_actor_ref"],
    )
    op.create_table(
        "generation_runs",
        sa.Column("run_id", sa.String(length=128), primary_key=True),
        sa.Column("request_ref", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("model", sa.String(length=256), nullable=False),
        sa.Column("prompt_version", sa.String(length=128), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_code", sa.String(length=128), nullable=True),
    )
    op.create_index("ix_generation_runs_request_ref", "generation_runs", ["request_ref"])
    op.create_table(
        "content_generation_results",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("request_ref", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("supersedes_result_ref", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("lesson_ref", sa.String(length=256), nullable=True),
        sa.Column("objective_refs", sa.JSON(), nullable=False),
        sa.Column("learning_need_refs", sa.JSON(), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("generation_metadata", sa.JSON(), nullable=False),
        sa.Column("generation_run", sa.JSON(), nullable=True),
        sa.Column("source_blueprint_ref", sa.String(length=256), nullable=True),
        sa.Column("course_authoring_request_ref", sa.String(length=128), nullable=True),
        sa.Column("generated_course", sa.JSON(), nullable=True),
        sa.Column("revision_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_content_generation_results_request_ref",
        "content_generation_results",
        ["request_ref"],
    )
    op.create_index(
        "ix_content_generation_results_course_authoring_request_ref",
        "content_generation_results",
        ["course_authoring_request_ref"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_content_generation_results_course_authoring_request_ref",
        table_name="content_generation_results",
    )
    op.drop_index("ix_content_generation_results_request_ref", table_name="content_generation_results")
    op.drop_table("content_generation_results")
    op.drop_index("ix_generation_runs_request_ref", table_name="generation_runs")
    op.drop_table("generation_runs")
    op.drop_index(
        "ix_course_authoring_requests_created_by_actor_ref",
        table_name="course_authoring_requests",
    )
    op.drop_table("course_authoring_requests")
