"""add PAI candidate aggregate and provenance relationships

Revision ID: 20260818_26
Revises: 20260818_25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_26"
down_revision: str | None = "20260818_25"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_actor_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("review_state", sa.String(length=32), nullable=False),
        sa.Column("current_profile_id", sa.String(length=36), nullable=True),
        sa.Column("current_profile_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_candidates_organization_id", "candidates", ["organization_id"])
    op.create_index("ix_candidates_status", "candidates", ["status"])
    op.create_index("ix_candidates_review_state", "candidates", ["review_state"])

    op.create_table(
        "candidate_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("document_kind", sa.String(length=16), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("attached_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("candidate_id", "document_id", name="uq_candidate_document"),
    )
    op.create_index("ix_candidate_documents_candidate_id", "candidate_documents", ["candidate_id"])
    op.create_index("ix_candidate_documents_document_id", "candidate_documents", ["document_id"])

    op.create_table(
        "candidate_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("review_state", sa.String(length=32), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("candidate_id", "profile_id", name="uq_candidate_profile"),
    )
    op.create_index("ix_candidate_profiles_candidate_id", "candidate_profiles", ["candidate_id"])
    op.create_index("ix_candidate_profiles_profile_id", "candidate_profiles", ["profile_id"])

    op.create_table(
        "candidate_claims",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("bucket", sa.String(length=32), nullable=False),
        sa.Column("claim_index", sa.Integer(), nullable=False),
        sa.Column("value", sa.String(length=2048), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_status", sa.String(length=32), nullable=False),
        sa.Column("context", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.UniqueConstraint(
            "candidate_id",
            "profile_id",
            "bucket",
            "claim_index",
            name="uq_candidate_claim_source",
        ),
    )
    op.create_index("ix_candidate_claims_candidate_id", "candidate_claims", ["candidate_id"])

    op.create_table(
        "candidate_evidence",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("claim_id", sa.Uuid(), sa.ForeignKey("candidate_claims.id"), nullable=False),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("source_locator", sa.JSON(), nullable=True),
        sa.Column("excerpt", sa.String(length=500), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("context", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
    )
    op.create_index("ix_candidate_evidence_candidate_id", "candidate_evidence", ["candidate_id"])
    op.create_index("ix_candidate_evidence_claim_id", "candidate_evidence", ["claim_id"])


def downgrade() -> None:
    op.drop_index("ix_candidate_evidence_claim_id", table_name="candidate_evidence")
    op.drop_index("ix_candidate_evidence_candidate_id", table_name="candidate_evidence")
    op.drop_table("candidate_evidence")
    op.drop_index("ix_candidate_claims_candidate_id", table_name="candidate_claims")
    op.drop_table("candidate_claims")
    op.drop_index("ix_candidate_profiles_profile_id", table_name="candidate_profiles")
    op.drop_index("ix_candidate_profiles_candidate_id", table_name="candidate_profiles")
    op.drop_table("candidate_profiles")
    op.drop_index("ix_candidate_documents_document_id", table_name="candidate_documents")
    op.drop_index("ix_candidate_documents_candidate_id", table_name="candidate_documents")
    op.drop_table("candidate_documents")
    op.drop_index("ix_candidates_review_state", table_name="candidates")
    op.drop_index("ix_candidates_status", table_name="candidates")
    op.drop_index("ix_candidates_organization_id", table_name="candidates")
    op.drop_table("candidates")
