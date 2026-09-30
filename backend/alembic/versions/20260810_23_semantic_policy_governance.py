"""add immutable semantic policy governance records and role bindings

Revision ID: 20260810_23
Revises: 20260810_22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260810_23"
down_revision: str | None = "20260810_22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "role_competency_profiles",
        sa.Column("semantic_policy_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "role_competency_profiles",
        sa.Column("semantic_policy_version", sa.String(length=64), nullable=True),
    )
    op.create_table(
        "semantic_policies",
        sa.Column("record_id", sa.String(length=256), primary_key=True),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("core_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("domain_pack_id", sa.String(length=128), nullable=False),
        sa.Column("domain_pack_version", sa.String(length=64), nullable=False),
        sa.Column("domain_pack_checksum", sa.String(length=256), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("reviewed_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("policy_id", "version", name="uq_semantic_policy_id_version"),
    )
    op.create_table(
        "semantic_policy_audit_events",
        sa.Column("id", sa.String(length=256), primary_key=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("semantic_policy_audit_events")
    op.drop_table("semantic_policies")
    op.drop_column("role_competency_profiles", "semantic_policy_version")
    op.drop_column("role_competency_profiles", "semantic_policy_id")
