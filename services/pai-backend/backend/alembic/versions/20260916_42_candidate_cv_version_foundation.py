"""add human-friendly candidate registry fields and authoritative CV versions

Revision ID: 20260916_42
Revises: 20260916_41
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260916_42"
down_revision: str | Sequence[str] | None = "20260916_41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("candidate_code", sa.String(length=32), nullable=True))
    op.add_column("candidates", sa.Column("display_name", sa.String(length=256), nullable=True))
    op.add_column("candidates", sa.Column("primary_email", sa.String(length=320), nullable=True))
    op.add_column("candidates", sa.Column("primary_phone", sa.String(length=64), nullable=True))
    op.execute(
        "UPDATE candidates SET candidate_code = 'CAN-' || upper(substr(replace(id::text, '-', ''), 1, 12)) "
        "WHERE candidate_code IS NULL"
    )
    op.alter_column("candidates", "candidate_code", nullable=False)
    op.create_index("ix_candidates_candidate_code", "candidates", ["candidate_code"], unique=True)

    op.create_table(
        "candidate_cvs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("candidate_id", name="uq_candidate_cv_candidate"),
    )
    op.create_table(
        "candidate_cv_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("candidate_cv_id", sa.Uuid(), sa.ForeignKey("candidate_cvs.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("created_by_actor_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("candidate_cv_id", "version", name="uq_candidate_cv_version"),
        sa.UniqueConstraint("document_id", name="uq_candidate_cv_version_document"),
    )
    op.create_index("ix_candidate_cv_versions_candidate_cv_id", "candidate_cv_versions", ["candidate_cv_id"])

    op.execute(
        """
        INSERT INTO candidate_cvs (id, candidate_id)
        SELECT gen_random_uuid(), candidate_id
        FROM candidate_documents
        WHERE document_kind = 'cv'
        GROUP BY candidate_id
        """
    )
    op.execute(
        """
        INSERT INTO candidate_cv_versions
            (id, candidate_cv_id, version, document_id, created_by_actor_id, created_at)
        SELECT gen_random_uuid(), cv.id,
               row_number() OVER (PARTITION BY cd.candidate_id ORDER BY cd.attached_at, cd.id),
               cd.document_id, c.created_by_actor_id, cd.attached_at
        FROM candidate_documents cd
        JOIN candidate_cvs cv ON cv.candidate_id = cd.candidate_id
        JOIN candidates c ON c.id = cd.candidate_id
        WHERE cd.document_kind = 'cv'
        """
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_cv_versions_candidate_cv_id", table_name="candidate_cv_versions")
    op.drop_table("candidate_cv_versions")
    op.drop_table("candidate_cvs")
    op.drop_index("ix_candidates_candidate_code", table_name="candidates")
    op.drop_column("candidates", "primary_phone")
    op.drop_column("candidates", "primary_email")
    op.drop_column("candidates", "display_name")
    op.drop_column("candidates", "candidate_code")
