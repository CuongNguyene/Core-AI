"""add candidate to LMS user identity bridge

Revision ID: 20260916_41
Revises: 20260907_40
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260916_41"
down_revision: str | Sequence[str] | None = "20260907_40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_identity_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("source_subject_ref", sa.String(length=256), nullable=False),
        sa.Column("organization_scope", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("authorization_users.id"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_candidate_identity_links_candidate_id",
        "candidate_identity_links",
        ["candidate_id"],
    )
    op.create_index(
        "ix_candidate_identity_links_organization_scope",
        "candidate_identity_links",
        ["organization_scope"],
    )
    op.create_index(
        "ix_candidate_identity_links_status",
        "candidate_identity_links",
        ["status"],
    )
    op.create_index(
        "uq_candidate_identity_links_active_candidate_lms",
        "candidate_identity_links",
        ["candidate_id"],
        unique=True,
        postgresql_where=sa.text("source_system = 'lms' AND status = 'ACTIVE'"),
    )
    op.create_index(
        "uq_candidate_identity_links_active_subject_lms",
        "candidate_identity_links",
        ["source_system", "source_subject_ref", "organization_scope"],
        unique=True,
        postgresql_where=sa.text("source_system = 'lms' AND status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index("uq_candidate_identity_links_active_subject_lms", table_name="candidate_identity_links")
    op.drop_index("uq_candidate_identity_links_active_candidate_lms", table_name="candidate_identity_links")
    op.drop_index("ix_candidate_identity_links_status", table_name="candidate_identity_links")
    op.drop_index("ix_candidate_identity_links_organization_scope", table_name="candidate_identity_links")
    op.drop_index("ix_candidate_identity_links_candidate_id", table_name="candidate_identity_links")
    op.drop_table("candidate_identity_links")
