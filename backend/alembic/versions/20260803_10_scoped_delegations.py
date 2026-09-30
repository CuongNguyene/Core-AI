"""Persist scoped competency verification delegations.

Revision ID: 20260803_10
Revises: 20260803_09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_10"
down_revision: str | Sequence[str] | None = "20260803_09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scoped_delegations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("permission", sa.String(64), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("competency_scope", sa.JSON(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("granted_by", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(256), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["authorization_users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["authorization_organizations.id"]),
        sa.ForeignKeyConstraint(["granted_by"], ["authorization_users.id"]),
    )
    op.create_index(
        "ix_delegation_active_lookup",
        "scoped_delegations",
        ["user_id", "permission", "organization_id", "status"],
    )
    op.create_index("ix_delegation_validity", "scoped_delegations", ["valid_from", "valid_until"])
    op.create_table(
        "authorization_audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("delegation_id", sa.Uuid()),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["authorization_users.id"]),
        sa.ForeignKeyConstraint(["delegation_id"], ["scoped_delegations.id"]),
    )


def downgrade() -> None:
    op.drop_table("authorization_audit_events")
    op.drop_index("ix_delegation_validity", table_name="scoped_delegations")
    op.drop_index("ix_delegation_active_lookup", table_name="scoped_delegations")
    op.drop_table("scoped_delegations")
