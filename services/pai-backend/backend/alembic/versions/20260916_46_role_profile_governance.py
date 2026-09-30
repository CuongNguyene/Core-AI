"""add stable RoleCompetencyProfile governance version and active pointer

Revision ID: 20260916_46
Revises: 20260916_45
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260916_46"
down_revision: str | Sequence[str] | None = "20260916_45"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "role_competency_profiles",
        sa.Column("governance_version", sa.Integer(), nullable=True),
    )
    op.add_column("roles", sa.Column("active_role_profile_id", sa.String(length=128), nullable=True))

    # Only the unambiguous one-profile-per-role case is backfilled. Legacy rows
    # without stable role lineage remain NULL by design.
    op.execute(
        sa.text(
            """
            UPDATE role_competency_profiles AS profile
            SET governance_version = 1
            WHERE profile.role_id IS NOT NULL
              AND profile.governance_version IS NULL
              AND (
                  SELECT count(*)
                  FROM role_competency_profiles AS sibling
                  WHERE sibling.role_id = profile.role_id
              ) = 1
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE roles AS role
            SET active_role_profile_id = profile.id
            FROM role_competency_profiles AS profile
            WHERE profile.role_id = role.id
              AND profile.status = 'active'
              AND profile.governance_version IS NOT NULL
              AND (
                  SELECT count(*)
                  FROM role_competency_profiles AS sibling
                  WHERE sibling.role_id = role.id
                    AND sibling.status = 'active'
              ) = 1
            """
        )
    )
    op.create_index(
        "uq_role_competency_profiles_role_governance_version",
        "role_competency_profiles",
        ["role_id", "governance_version"],
        unique=True,
        postgresql_where=sa.text("role_id IS NOT NULL AND governance_version IS NOT NULL"),
    )
    op.create_index(
        "ix_roles_active_role_profile_id",
        "roles",
        ["active_role_profile_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_roles_active_role_profile_id", table_name="roles")
    op.drop_index(
        "uq_role_competency_profiles_role_governance_version",
        table_name="role_competency_profiles",
    )
    op.drop_column("roles", "active_role_profile_id")
    op.drop_column("role_competency_profiles", "governance_version")
