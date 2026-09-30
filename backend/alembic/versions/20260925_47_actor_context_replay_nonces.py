"""persist signed actor-context nonces across API instances

Revision ID: 20260925_47
Revises: 20260916_46, 20260917_42
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260925_47"
down_revision: str | Sequence[str] | None = ("20260916_46", "20260917_42")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "actor_context_nonces",
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("nonce"),
    )
    op.create_index("ix_actor_context_nonces_expires_at", "actor_context_nonces", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_actor_context_nonces_expires_at", table_name="actor_context_nonces")
    op.drop_table("actor_context_nonces")
