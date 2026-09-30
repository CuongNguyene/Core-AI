"""Add extraction acceptance metadata and revision constraints.

Revision ID: 20260731_03
Revises: 20260731_02
Create Date: 2026-07-31 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_03"
down_revision: str | Sequence[str] | None = "20260731_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "extraction_profiles",
        sa.Column("accepted_by", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "extraction_profiles",
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "extraction_profiles",
        sa.Column("supersedes_profile_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_extraction_profiles_supersedes_profile_id",
        "extraction_profiles",
        "extraction_profiles",
        ["supersedes_profile_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_extraction_profiles_job_version",
        "extraction_profiles",
        ["job_id", "version"],
    )
    op.create_index(
        "ix_extraction_profiles_supersedes_profile_id",
        "extraction_profiles",
        ["supersedes_profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_extraction_profiles_review_state",
        "extraction_profiles",
        ["review_state"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_extraction_profiles_review_state", table_name="extraction_profiles")
    op.drop_index("ix_extraction_profiles_supersedes_profile_id", table_name="extraction_profiles")
    op.drop_constraint("uq_extraction_profiles_job_version", "extraction_profiles", type_="unique")
    op.drop_constraint(
        "fk_extraction_profiles_supersedes_profile_id",
        "extraction_profiles",
        type_="foreignkey",
    )
    op.drop_column("extraction_profiles", "supersedes_profile_id")
    op.drop_column("extraction_profiles", "accepted_at")
    op.drop_column("extraction_profiles", "accepted_by")
