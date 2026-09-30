"""add forward-safe role and JD lineage to role profiles

Revision ID: 20260916_45
Revises: 20260916_44
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260916_45"
down_revision: str | Sequence[str] | None = "20260916_44"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("role_profile_drafts", sa.Column("role_id", sa.UUID(), nullable=True))
    op.add_column(
        "role_profile_drafts", sa.Column("role_jd_version_id", sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        "fk_role_profile_drafts_role_id",
        "role_profile_drafts",
        "roles",
        ["role_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_role_profile_drafts_role_jd_version_id",
        "role_profile_drafts",
        "role_jd_versions",
        ["role_jd_version_id"],
        ["id"],
    )
    op.create_index("ix_role_profile_drafts_role_id", "role_profile_drafts", ["role_id"])
    op.create_index(
        "ix_role_profile_drafts_role_jd_version_id",
        "role_profile_drafts",
        ["role_jd_version_id"],
    )

    op.add_column("role_competency_profiles", sa.Column("role_id", sa.UUID(), nullable=True))
    op.add_column(
        "role_competency_profiles", sa.Column("role_jd_version_id", sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        "fk_role_competency_profiles_role_id",
        "role_competency_profiles",
        "roles",
        ["role_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_role_competency_profiles_role_jd_version_id",
        "role_competency_profiles",
        "role_jd_versions",
        ["role_jd_version_id"],
        ["id"],
    )
    op.create_index("ix_role_competency_profiles_role_id", "role_competency_profiles", ["role_id"])
    op.create_index(
        "ix_role_competency_profiles_role_jd_version_id",
        "role_competency_profiles",
        ["role_jd_version_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_role_competency_profiles_role_jd_version_id", table_name="role_competency_profiles")
    op.drop_index("ix_role_competency_profiles_role_id", table_name="role_competency_profiles")
    op.drop_constraint("fk_role_competency_profiles_role_jd_version_id", "role_competency_profiles", type_="foreignkey")
    op.drop_constraint("fk_role_competency_profiles_role_id", "role_competency_profiles", type_="foreignkey")
    op.drop_column("role_competency_profiles", "role_jd_version_id")
    op.drop_column("role_competency_profiles", "role_id")
    op.drop_index("ix_role_profile_drafts_role_jd_version_id", table_name="role_profile_drafts")
    op.drop_index("ix_role_profile_drafts_role_id", table_name="role_profile_drafts")
    op.drop_constraint("fk_role_profile_drafts_role_jd_version_id", "role_profile_drafts", type_="foreignkey")
    op.drop_constraint("fk_role_profile_drafts_role_id", "role_profile_drafts", type_="foreignkey")
    op.drop_column("role_profile_drafts", "role_jd_version_id")
    op.drop_column("role_profile_drafts", "role_id")
