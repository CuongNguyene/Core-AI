"""Add fixture extraction jobs, profiles and safe audit metadata.

Revision ID: 20260731_02
Revises: 20260731_01
Create Date: 2026-07-31 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_02"
down_revision: str | Sequence[str] | None = "20260731_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "extraction_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=128), nullable=False),
        sa.Column("document_kind", sa.String(length=16), nullable=False),
        sa.Column("owner_actor_id", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_category", sa.String(length=128), nullable=True),
        sa.Column("profile_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_extraction_jobs_status", "extraction_jobs", ["status"], unique=False)
    op.create_table(
        "extraction_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=128), nullable=False),
        sa.Column("document_kind", sa.String(length=16), nullable=False),
        sa.Column("owner_actor_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("review_state", sa.String(length=32), nullable=False),
        sa.Column("normalized_output", sa.JSON(), nullable=False),
        sa.Column("audit_metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["extraction_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_extraction_profiles_job_id", "extraction_profiles", ["job_id"], unique=False
    )
    op.create_index(
        "ix_extraction_profiles_owner_actor_id",
        "extraction_profiles",
        ["owner_actor_id"],
        unique=False,
    )
    op.create_table(
        "extraction_audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=True),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["job_id"], ["extraction_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("extraction_audit_events")
    op.drop_index("ix_extraction_profiles_owner_actor_id", table_name="extraction_profiles")
    op.drop_index("ix_extraction_profiles_job_id", table_name="extraction_profiles")
    op.drop_table("extraction_profiles")
    op.drop_index("ix_extraction_jobs_status", table_name="extraction_jobs")
    op.drop_table("extraction_jobs")
