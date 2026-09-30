"""persist role profile draft quality detail and approval eligibility

Revision ID: 20260807_20
Revises: 20260807_19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260807_20"
down_revision: str | None = "20260807_19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("role_profile_drafts", "role_profile_draft_versions"):
        op.add_column(
            table,
            sa.Column("approval_eligibility", sa.JSON(), nullable=False, server_default="{}"),
        )
        op.add_column(
            table,
            sa.Column("duplicate_candidate_groups", sa.JSON(), nullable=False, server_default="[]"),
        )


def downgrade() -> None:
    for table in ("role_profile_draft_versions", "role_profile_drafts"):
        op.drop_column(table, "duplicate_candidate_groups")
        op.drop_column(table, "approval_eligibility")
