"""add structured candidate source identity, snapshots and evidence

Revision ID: 20261006_52
Revises: 20261005_51
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261006_52"
down_revision: str | Sequence[str] | None = "20261005_51"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_external_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(64), nullable=False),
        sa.Column("external_company_ref", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["authorization_organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_system", "external_company_ref", name="uq_org_external_source_ref"
        ),
    )
    op.create_index(
        "ix_organization_external_mappings_organization_id",
        "organization_external_mappings",
        ["organization_id"],
    )

    op.create_table(
        "candidate_source_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(64), nullable=False),
        sa.Column("employee_ref", sa.String(255), nullable=False),
        sa.Column("schema_id", sa.String(128), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("source_snapshot_ref", sa.String(255), nullable=True),
        sa.Column("source_version", sa.JSON(), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("ordering_state", sa.String(32), nullable=False),
        sa.Column("previous_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["authorization_organizations.id"]),
        sa.ForeignKeyConstraint(["previous_snapshot_id"], ["candidate_source_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "candidate_id", "fingerprint", name="uq_candidate_source_snapshot_fingerprint"
        ),
    )
    op.create_index(
        "ix_candidate_source_snapshot_candidate_created",
        "candidate_source_snapshots",
        ["candidate_id", "ingested_at"],
    )

    op.create_table(
        "candidate_external_employee_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(64), nullable=False),
        sa.Column("employee_ref", sa.String(255), nullable=False),
        sa.Column("current_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["authorization_organizations.id"]),
        sa.ForeignKeyConstraint(["current_snapshot_id"], ["candidate_source_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "candidate_id", "source_system", name="uq_candidate_external_identity_candidate_source"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "source_system",
            "employee_ref",
            name="uq_candidate_external_employee_identity",
        ),
    )

    op.create_table(
        "candidate_structured_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(64), nullable=False),
        sa.Column("employee_ref", sa.String(255), nullable=False),
        sa.Column("source_record_ref", sa.String(255), nullable=True),
        sa.Column("source_field_path", sa.String(512), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_version", sa.JSON(), nullable=True),
        sa.Column("source_value", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["candidate_source_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_candidate_structured_evidence_snapshot",
        "candidate_structured_evidence",
        ["snapshot_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_candidate_structured_evidence_snapshot", table_name="candidate_structured_evidence"
    )
    op.drop_table("candidate_structured_evidence")
    op.drop_table("candidate_external_employee_identities")
    op.drop_index(
        "ix_candidate_source_snapshot_candidate_created", table_name="candidate_source_snapshots"
    )
    op.drop_table("candidate_source_snapshots")
    op.drop_index(
        "ix_organization_external_mappings_organization_id",
        table_name="organization_external_mappings",
    )
    op.drop_table("organization_external_mappings")
