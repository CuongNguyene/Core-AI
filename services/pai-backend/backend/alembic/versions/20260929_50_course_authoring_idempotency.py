"""add idempotency key to course authoring requests

Revision ID: 20260929_50
Revises: 20260925_49
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260929_50"
down_revision: str | Sequence[str] | None = "20260925_49"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "course_authoring_requests",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.create_unique_constraint(
        "uq_course_authoring_requests_idempotency_key",
        "course_authoring_requests",
        ["idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_course_authoring_requests_idempotency_key",
        "course_authoring_requests",
        type_="unique",
    )
    op.drop_column("course_authoring_requests", "idempotency_key")
