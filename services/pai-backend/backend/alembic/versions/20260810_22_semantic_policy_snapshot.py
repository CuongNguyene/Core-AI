"""persist semantic policy metadata and immutable legacy mappings

Revision ID: 20260810_22
Revises: 20260810_21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260810_22"
down_revision: str | None = "20260810_21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "role_competency_profiles",
        sa.Column("semantic_core_version", sa.String(length=64)),
    )
    op.add_column(
        "role_competency_profiles",
        sa.Column("semantic_pack_refs", sa.JSON()),
    )
    op.add_column(
        "capability_gap_portfolios",
        sa.Column("semantic_policy", sa.JSON()),
    )
    op.create_table(
        "role_profile_semantic_policy_mappings",
        sa.Column("role_profile_id", sa.String(length=128), primary_key=True),
        sa.Column("role_profile_version", sa.String(length=64), primary_key=True),
        sa.Column("core_version", sa.String(length=64), nullable=False),
        sa.Column("pack_refs", sa.JSON(), nullable=False),
        sa.Column("selection_source", sa.String(length=64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("role_profile_semantic_policy_mappings")
    op.drop_column("capability_gap_portfolios", "semantic_policy")
    op.drop_column("role_competency_profiles", "semantic_pack_refs")
    op.drop_column("role_competency_profiles", "semantic_core_version")
