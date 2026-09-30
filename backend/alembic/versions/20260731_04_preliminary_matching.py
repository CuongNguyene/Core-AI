"""Add preliminary matching persistence.

Revision ID: 20260731_04
Revises: 20260731_03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_04"
down_revision: str | Sequence[str] | None = "20260731_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "role_competency_profiles",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source_jd_profile_id", sa.String(36), nullable=False),
        sa.Column("source_jd_profile_version", sa.Integer(), nullable=False),
        sa.Column("rule_set_version", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.UniqueConstraint("id", "version", name="uq_role_profile_id_version"),
    )
    op.create_index("ix_role_competency_profiles_status", "role_competency_profiles", ["status"])
    op.create_table(
        "preliminary_matches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cv_profile_id", sa.String(36), nullable=False),
        sa.Column("cv_profile_version", sa.Integer(), nullable=False),
        sa.Column("jd_profile_id", sa.String(36), nullable=False),
        sa.Column("jd_profile_version", sa.Integer(), nullable=False),
        sa.Column("role_profile_id", sa.String(128), nullable=False),
        sa.Column("role_profile_version", sa.String(64), nullable=False),
        sa.Column("rule_set_version", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("criterion_results", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["cv_profile_id"], ["extraction_profiles.id"]),
        sa.ForeignKeyConstraint(["jd_profile_id"], ["extraction_profiles.id"]),
    )
    op.create_table(
        "match_evidence_allocations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("match_id", sa.String(36), nullable=False),
        sa.Column("evidence_id", sa.String(64), nullable=False),
        sa.Column("requirement_id", sa.String(128), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["preliminary_matches.id"]),
        sa.UniqueConstraint("match_id", "evidence_id", name="uq_match_decisive_evidence"),
    )
    op.create_table(
        "matching_audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("match_id", sa.String(36), nullable=True),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["preliminary_matches.id"]),
    )


def downgrade() -> None:
    op.drop_table("matching_audit_events")
    op.drop_table("match_evidence_allocations")
    op.drop_table("preliminary_matches")
    op.drop_index("ix_role_competency_profiles_status", table_name="role_competency_profiles")
    op.drop_table("role_competency_profiles")
