"""Preserve immutable role competency profile versions.

Revision ID: 20260803_07
Revises: 20260803_06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_07"
down_revision: str | Sequence[str] | None = "20260803_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("role_competency_profiles", sa.Column("record_id", sa.String(256), nullable=True))
    op.execute("UPDATE role_competency_profiles SET record_id = id || ':' || version")
    op.alter_column("role_competency_profiles", "record_id", nullable=False)
    op.drop_constraint("role_competency_profiles_pkey", "role_competency_profiles", type_="primary")
    op.create_primary_key(
        "pk_role_competency_profiles_record_id", "role_competency_profiles", ["record_id"]
    )
    op.create_index("ix_role_competency_profiles_id", "role_competency_profiles", ["id"])


def downgrade() -> None:
    op.drop_index("ix_role_competency_profiles_id", table_name="role_competency_profiles")
    op.drop_constraint(
        "pk_role_competency_profiles_record_id", "role_competency_profiles", type_="primary"
    )
    op.create_primary_key("role_competency_profiles_pkey", "role_competency_profiles", ["id"])
    op.drop_column("role_competency_profiles", "record_id")
