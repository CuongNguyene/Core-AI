"""Require UUID actor references for development reset.

Revision ID: 20260803_09
Revises: 20260803_08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260803_09"
down_revision: str | Sequence[str] | None = "20260803_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Development-only legacy actor strings have no approved UUID mapping.
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM extraction_jobs WHERE owner_actor_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
          THEN RAISE EXCEPTION 'Reset development database before UUID actor migration; legacy actor strings cannot be mapped safely'; END IF;
        END $$;
        """
    )
    for table, column in (
        ("extraction_jobs", "owner_actor_id"),
        ("extraction_profiles", "owner_actor_id"),
        ("extraction_profiles", "accepted_by"),
        ("extraction_audit_events", "actor_id"),
        ("preliminary_matches", "actor_id"),
        ("matching_audit_events", "actor_id"),
    ):
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE uuid USING {column}::uuid")


def downgrade() -> None:
    for table, column in (
        ("matching_audit_events", "actor_id"),
        ("preliminary_matches", "actor_id"),
        ("extraction_audit_events", "actor_id"),
        ("extraction_profiles", "accepted_by"),
        ("extraction_profiles", "owner_actor_id"),
        ("extraction_jobs", "owner_actor_id"),
    ):
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE varchar(128) USING {column}::varchar"
        )
