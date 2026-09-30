"""add reviewer-controlled role profile authoring

Revision ID: 20260806_18
Revises: 20260806_17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260806_18"
down_revision: str | None = "20260806_17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "role_profile_drafts",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("source_jd_profile_id", sa.String(length=36), nullable=False),
        sa.Column("source_jd_profile_version", sa.Integer(), nullable=False),
        sa.Column("owner_actor_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=256)),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("quality_gate", sa.JSON(), nullable=False),
        sa.Column("approved_role_profile_id", sa.String(length=128)),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["source_jd_profile_id"], ["extraction_profiles.id"]),
    )
    op.create_index(
        "ix_role_profile_drafts_source_jd_profile_id",
        "role_profile_drafts",
        ["source_jd_profile_id"],
    )
    op.create_index(
        "ix_role_profile_drafts_owner_actor_id", "role_profile_drafts", ["owner_actor_id"]
    )
    op.create_index(
        "ix_role_profile_drafts_organization_id", "role_profile_drafts", ["organization_id"]
    )
    op.create_index("ix_role_profile_drafts_status", "role_profile_drafts", ["status"])
    op.create_table(
        "role_profile_draft_versions",
        sa.Column("record_id", sa.String(length=256), primary_key=True),
        sa.Column("draft_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=256)),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("quality_gate", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["draft_id"], ["role_profile_drafts.id"]),
    )
    op.create_index(
        "ix_role_profile_draft_versions_draft_id", "role_profile_draft_versions", ["draft_id"]
    )
    op.create_table(
        "role_profile_draft_audits",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("draft_id", sa.String(length=128), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["draft_id"], ["role_profile_drafts.id"]),
    )
    op.create_index(
        "ix_role_profile_draft_audits_draft_id", "role_profile_draft_audits", ["draft_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_role_profile_draft_audits_draft_id", table_name="role_profile_draft_audits")
    op.drop_table("role_profile_draft_audits")
    op.drop_index(
        "ix_role_profile_draft_versions_draft_id", table_name="role_profile_draft_versions"
    )
    op.drop_table("role_profile_draft_versions")
    for index in (
        "ix_role_profile_drafts_status",
        "ix_role_profile_drafts_organization_id",
        "ix_role_profile_drafts_owner_actor_id",
        "ix_role_profile_drafts_source_jd_profile_id",
    ):
        op.drop_index(index, table_name="role_profile_drafts")
    op.drop_table("role_profile_drafts")
