"""persist JD requirement source schema metadata and findings

Revision ID: 20260807_19
Revises: 20260806_18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260807_19"
down_revision: str | None = "20260806_18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("role_profile_drafts", "role_profile_draft_versions"):
        op.add_column(
            table,
            sa.Column("source_schema", sa.String(length=64), nullable=False, server_default="legacy_v1"),
        )
        op.add_column(
            table,
            sa.Column(
                "source_version",
                sa.String(length=32),
                nullable=False,
                server_default="1.1",
            ),
        )
        op.add_column(
            table,
            sa.Column("authoring_findings", sa.JSON(), nullable=False, server_default="[]"),
        )


def downgrade() -> None:
    for table in ("role_profile_draft_versions", "role_profile_drafts"):
        op.drop_column(table, "authoring_findings")
        op.drop_column(table, "source_version")
        op.drop_column(table, "source_schema")
