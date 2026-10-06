"""add source revision ordering to candidate snapshots

Revision ID: 20261006_53
Revises: 20261006_52
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261006_53"
down_revision: str | Sequence[str] | None = "20261006_52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SNAPSHOT_IDENTITY_FK = "fk_candidate_source_snapshot_external_identity"
SNAPSHOT_IDENTITY_REQUIRED = "ck_candidate_source_snapshot_identity_required"
SOURCE_REVISION_POSITIVE = "ck_candidate_source_snapshot_revision_positive"
IDENTITY_REVISION_UNIQUE = "uq_candidate_source_snapshot_identity_revision"


def _validate_snapshot_identity_matches(connection: sa.Connection) -> None:
    snapshots = sa.table(
        "candidate_source_snapshots",
        sa.column("id"),
        sa.column("candidate_id"),
        sa.column("organization_id"),
        sa.column("source_system"),
        sa.column("employee_ref"),
    )
    identities = sa.table(
        "candidate_external_employee_identities",
        sa.column("id"),
        sa.column("candidate_id"),
        sa.column("organization_id"),
        sa.column("source_system"),
        sa.column("employee_ref"),
    )
    identity_match = sa.and_(
        identities.c.candidate_id == snapshots.c.candidate_id,
        identities.c.organization_id == snapshots.c.organization_id,
        identities.c.source_system == snapshots.c.source_system,
        identities.c.employee_ref == snapshots.c.employee_ref,
    )
    invalid = connection.execute(
        sa.select(snapshots.c.id, sa.func.count(identities.c.id).label("identity_count"))
        .select_from(snapshots.outerjoin(identities, identity_match))
        .group_by(snapshots.c.id)
        .having(sa.func.count(identities.c.id) != 1)
        .limit(1)
    ).first()
    if invalid is not None:
        raise RuntimeError(
            "Cannot backfill candidate source snapshot external identity: "
            f"snapshot {invalid.id} matched {invalid.identity_count} external employee identities; "
            "every snapshot must match exactly one."
        )


def upgrade() -> None:
    connection = op.get_bind()
    _validate_snapshot_identity_matches(connection)

    op.add_column(
        "candidate_source_snapshots",
        sa.Column("external_identity_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "candidate_source_snapshots",
        sa.Column("source_revision", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "candidate_source_snapshots",
        sa.Column("content_fingerprint", sa.String(64), nullable=True),
    )
    op.execute(
        sa.text(
            """
        UPDATE candidate_source_snapshots
        SET external_identity_id = (
            SELECT identity.id
            FROM candidate_external_employee_identities AS identity
            WHERE identity.candidate_id = candidate_source_snapshots.candidate_id
              AND identity.organization_id = candidate_source_snapshots.organization_id
              AND identity.source_system = candidate_source_snapshots.source_system
              AND identity.employee_ref = candidate_source_snapshots.employee_ref
        )
        """
        )
    )
    unresolved = connection.execute(
        sa.text(
            "SELECT id FROM candidate_source_snapshots WHERE external_identity_id IS NULL LIMIT 1"
        )
    ).first()
    if unresolved is not None:
        raise RuntimeError(
            "Cannot enforce candidate source snapshot external identity: "
            f"snapshot {unresolved.id} was not backfilled."
        )

    with op.batch_alter_table("candidate_source_snapshots") as batch:
        batch.alter_column("external_identity_id", existing_type=sa.Uuid(), nullable=False)
        batch.create_foreign_key(
            SNAPSHOT_IDENTITY_FK,
            "candidate_external_employee_identities",
            ["external_identity_id"],
            ["id"],
        )
        batch.create_check_constraint(
            SNAPSHOT_IDENTITY_REQUIRED,
            "external_identity_id IS NOT NULL",
        )
        batch.create_check_constraint(
            SOURCE_REVISION_POSITIVE,
            "source_revision IS NULL OR source_revision > 0",
        )
        batch.create_unique_constraint(
            IDENTITY_REVISION_UNIQUE,
            ["external_identity_id", "source_revision"],
        )
    op.create_index(
        "ix_candidate_source_snapshot_external_identity_id",
        "candidate_source_snapshots",
        ["external_identity_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_candidate_source_snapshot_external_identity_id",
        table_name="candidate_source_snapshots",
    )
    with op.batch_alter_table("candidate_source_snapshots") as batch:
        batch.drop_constraint(IDENTITY_REVISION_UNIQUE, type_="unique")
        batch.drop_constraint(SOURCE_REVISION_POSITIVE, type_="check")
        batch.drop_constraint(SNAPSHOT_IDENTITY_REQUIRED, type_="check")
        batch.drop_constraint(SNAPSHOT_IDENTITY_FK, type_="foreignkey")
        batch.drop_column("content_fingerprint")
        batch.drop_column("source_revision")
        batch.drop_column("external_identity_id")
