"""Persist preliminary gap approvals and versioned learning blueprints.

Revision ID: 20260803_12
Revises: 20260803_11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_12"
down_revision: str | Sequence[str] | None = "20260803_11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "preliminary_matches",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "preliminary_matches",
        sa.Column("approved_gap_ids", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column("preliminary_matches", sa.Column("reviewed_by", sa.Uuid(), nullable=True))
    op.add_column(
        "preliminary_matches",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "learning_paths",
        sa.Column("id", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("target_profile_id", sa.String(128), nullable=False),
        sa.Column("target_profile_version", sa.String(64), nullable=False),
        sa.Column("preliminary_match_id", sa.String(128), nullable=False),
        sa.Column("verified_competency_record_ids", sa.JSON(), nullable=False),
        sa.Column("approved_gap_ids", sa.JSON(), nullable=False),
        sa.Column("development_goal", sa.String(500), nullable=False),
        sa.Column("target_completion_date", sa.Date(), nullable=False),
        sa.Column("objectives", sa.JSON(), nullable=False),
        sa.Column("prerequisite_nodes", sa.JSON(), nullable=False),
        sa.Column("prerequisite_edges", sa.JSON(), nullable=False),
        sa.Column("learning_objects", sa.JSON(), nullable=False),
        sa.Column("lessons", sa.JSON(), nullable=False),
        sa.Column("modules", sa.JSON(), nullable=False),
        sa.Column("blueprints", sa.JSON(), nullable=False),
        sa.Column("generator_version", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", "version"),
        sa.UniqueConstraint("id", "version", name="uq_learning_path_version"),
    )
    op.create_index("ix_learning_paths_status", "learning_paths", ["status"])
    op.create_index("ix_learning_paths_subject_id", "learning_paths", ["subject_id"])
    op.create_index("ix_learning_paths_organization_id", "learning_paths", ["organization_id"])
    op.create_index("ix_learning_paths_target_profile_id", "learning_paths", ["target_profile_id"])
    op.create_table(
        "learning_audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("path_id", sa.String(128), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_learning_audit_events_path_id", "learning_audit_events", ["path_id"])


def downgrade() -> None:
    op.drop_index("ix_learning_audit_events_path_id", table_name="learning_audit_events")
    op.drop_table("learning_audit_events")
    op.drop_index("ix_learning_paths_target_profile_id", table_name="learning_paths")
    op.drop_index("ix_learning_paths_organization_id", table_name="learning_paths")
    op.drop_index("ix_learning_paths_subject_id", table_name="learning_paths")
    op.drop_index("ix_learning_paths_status", table_name="learning_paths")
    op.drop_table("learning_paths")
    op.drop_column("preliminary_matches", "reviewed_at")
    op.drop_column("preliminary_matches", "reviewed_by")
    op.drop_column("preliminary_matches", "approved_gap_ids")
    op.drop_column("preliminary_matches", "version")
