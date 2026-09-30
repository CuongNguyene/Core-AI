"""add learning path integration idempotency fields

Revision ID: 20260821_31
Revises: 20260821_30
"""

import sqlalchemy as sa
from alembic import op

revision = "20260821_31"
down_revision = "20260821_30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("learning_paths", sa.Column("idempotency_key", sa.String(128), nullable=True))
    op.add_column("learning_paths", sa.Column("request_fingerprint", sa.String(128), nullable=True))
    op.create_unique_constraint("uq_learning_paths_idempotency_key", "learning_paths", ["idempotency_key"])


def downgrade() -> None:
    op.drop_constraint("uq_learning_paths_idempotency_key", "learning_paths", type_="unique")
    op.drop_column("learning_paths", "request_fingerprint")
    op.drop_column("learning_paths", "idempotency_key")
