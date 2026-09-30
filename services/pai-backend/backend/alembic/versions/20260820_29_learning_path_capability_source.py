"""add capability analysis learning path source metadata

Revision ID: 20260820_29
Revises: 20260819_28
"""

import sqlalchemy as sa

from alembic import op

revision = "20260820_29"
down_revision = "20260819_28"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("learning_paths", sa.Column("source_type", sa.String(32), nullable=False, server_default="verified"))
    op.add_column("learning_paths", sa.Column("capability_analysis_id", sa.String(128), nullable=True))
    op.add_column("learning_paths", sa.Column("capability_analysis_version", sa.Integer(), nullable=True))
    op.add_column("learning_paths", sa.Column("source_candidate_id", sa.Uuid(), nullable=True))
    op.add_column("learning_paths", sa.Column("source_profile_id", sa.String(128), nullable=True))
    op.add_column("learning_paths", sa.Column("source_profile_version", sa.Integer(), nullable=True))
    op.add_column("learning_paths", sa.Column("source_target_id", sa.String(128), nullable=True))
    op.add_column("learning_paths", sa.Column("source_target_version", sa.String(64), nullable=True))
    op.add_column("learning_paths", sa.Column("source_gap_ids", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("learning_paths", sa.Column("source_evidence_refs", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("learning_paths", sa.Column("source_recommendation_refs", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("learning_paths", sa.Column("validation", sa.JSON(), nullable=False, server_default='{"valid": true, "ready_for_review": true, "findings": []}'))
    op.create_index("ix_learning_paths_capability_analysis_id", "learning_paths", ["capability_analysis_id"])


def downgrade() -> None:
    op.drop_index("ix_learning_paths_capability_analysis_id", table_name="learning_paths")
    for name in (
        "validation", "source_recommendation_refs", "source_evidence_refs", "source_gap_ids",
        "source_target_version", "source_target_id", "source_profile_version", "source_profile_id",
        "source_candidate_id", "capability_analysis_version", "capability_analysis_id", "source_type",
    ):
        op.drop_column("learning_paths", name)
