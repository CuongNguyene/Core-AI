"""document metadata and object storage boundary

Revision ID: 20260804_14
Revises: 20260803_13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260804_14"
down_revision: str | None = "20260803_13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_actor_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("document_kind", sa.String(length=16), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("object_key", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index("ix_documents_owner_actor_id", "documents", ["owner_actor_id"])
    op.create_index("ix_documents_organization_id", "documents", ["organization_id"])
    op.create_index("ix_documents_status", "documents", ["status"])


def downgrade() -> None:
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_index("ix_documents_organization_id", table_name="documents")
    op.drop_index("ix_documents_owner_actor_id", table_name="documents")
    op.drop_table("documents")
