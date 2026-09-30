"""Add development authorization subject persistence.

Revision ID: 20260803_08
Revises: 20260803_07
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_08"
down_revision: str | Sequence[str] | None = "20260803_07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "authorization_users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("username", sa.String(128), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "authorization_organizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["authorization_users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["authorization_organizations.id"]),
        sa.UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),
    )
    op.create_table(
        "user_role_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("granted_by", sa.Uuid(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["authorization_users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["authorization_organizations.id"]),
        sa.ForeignKeyConstraint(["granted_by"], ["authorization_users.id"]),
        sa.UniqueConstraint("user_id", "organization_id", "role", name="uq_user_org_role"),
    )
    op.create_index("ix_membership_active_user", "organization_memberships", ["user_id", "status"])
    op.create_index(
        "ix_role_assignment_active_user",
        "user_role_assignments",
        ["user_id", "organization_id", "status"],
    )
    user_table = sa.table(
        "authorization_users",
        sa.column("id", sa.Uuid()),
        sa.column("display_name", sa.String()),
        sa.column("username", sa.String()),
        sa.column("status", sa.String()),
        sa.column("version", sa.Integer()),
    )
    organization_table = sa.table(
        "authorization_organizations",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("status", sa.String()),
        sa.column("version", sa.Integer()),
    )
    membership_table = sa.table(
        "organization_memberships",
        sa.column("id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("organization_id", sa.Uuid()),
        sa.column("status", sa.String()),
    )
    role_table = sa.table(
        "user_role_assignments",
        sa.column("id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("organization_id", sa.Uuid()),
        sa.column("role", sa.String()),
        sa.column("status", sa.String()),
        sa.column("granted_by", sa.Uuid()),
    )
    organization_id = UUID("00000000-0000-0000-0000-000000000001")
    admin_id = UUID("00000000-0000-0000-0000-000000000002")
    user_ids = [
        admin_id,
        *[UUID(f"00000000-0000-0000-0000-00000000000{value}") for value in range(3, 8)],
    ]
    op.bulk_insert(
        organization_table,
        [
            {
                "id": organization_id,
                "code": "ORG-PAI",
                "name": "PAI",
                "status": "active",
                "version": 1,
            }
        ],
    )
    op.bulk_insert(
        user_table,
        [
            {
                "id": user_id,
                "display_name": name,
                "username": username,
                "status": "disabled" if user_id.int % 10 == 7 else "active",
                "version": 1,
            }
            for user_id, name, username in zip(
                user_ids,
                ["Admin", "SME", "Reviewer", "Learner", "Authorized SME", "Disabled"],
                ["admin", "sme", "reviewer", "learner", "authorized-sme", "disabled"],
                strict=True,
            )
        ],
    )
    op.bulk_insert(
        membership_table,
        [
            {
                "id": UUID(f"10000000-0000-0000-0000-00000000000{index}"),
                "user_id": user_id,
                "organization_id": organization_id,
                "status": "active",
            }
            for index, user_id in enumerate(user_ids, start=1)
        ],
    )
    op.bulk_insert(
        role_table,
        [
            {
                "id": UUID(f"20000000-0000-0000-0000-00000000000{index}"),
                "user_id": user_id,
                "organization_id": organization_id,
                "role": role,
                "status": "active",
                "granted_by": admin_id,
            }
            for index, (user_id, role) in enumerate(
                zip(user_ids[:5], ["admin", "sme", "reviewer", "learner", "sme"], strict=True),
                start=1,
            )
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_role_assignment_active_user", table_name="user_role_assignments")
    op.drop_index("ix_membership_active_user", table_name="organization_memberships")
    op.drop_table("user_role_assignments")
    op.drop_table("organization_memberships")
    op.drop_table("authorization_organizations")
    op.drop_table("authorization_users")
