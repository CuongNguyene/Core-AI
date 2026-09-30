"""Persist credential policy, request, issuance and audit snapshots."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_13"
down_revision: str | Sequence[str] | None = "20260803_12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "credential_policies",
        sa.Column("record_id", sa.Uuid(), primary_key=True),
        sa.Column("policy_id", sa.String(128), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("credential_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("valid_for_days", sa.Integer(), nullable=False),
        sa.Column("allow_duplicate_active", sa.Boolean(), nullable=False),
        sa.Column("requires_distinct_approver_and_issuer", sa.Boolean(), nullable=False),
        sa.Column("competency_id", sa.String(128)),
        sa.Column("minimum_level", sa.Integer()),
        sa.UniqueConstraint("policy_id", "version", name="uq_credential_policy_version"),
    )
    op.create_index("ix_credential_policies_policy_id", "credential_policies", ["policy_id"])
    op.create_index("ix_credential_policies_status", "credential_policies", ["status"])
    op.create_table(
        "credential_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("policy_id", sa.String(128), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("credential_type", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source_reference_id", sa.String(512)),
        sa.Column("eligibility", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("approver_id", sa.Uuid()),
        sa.Column("issuer_id", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_credential_requests_subject_id", "credential_requests", ["subject_id"])
    op.create_index("ix_credential_requests_status", "credential_requests", ["status"])
    op.create_table(
        "credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.String(128), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("credential_type", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("issued_by", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["credential_requests.id"]),
        sa.UniqueConstraint("request_id", name="uq_credential_request"),
    )
    op.create_index("ix_credentials_subject_id", "credentials", ["subject_id"])
    op.create_index("ix_credentials_status", "credentials", ["status"])
    op.create_table(
        "credential_audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("request_id", sa.Uuid()),
        sa.Column("credential_id", sa.Uuid()),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["request_id"], ["credential_requests.id"]),
        sa.ForeignKeyConstraint(["credential_id"], ["credentials.id"]),
    )


def downgrade() -> None:
    op.drop_table("credential_audit_events")
    op.drop_index("ix_credentials_status", table_name="credentials")
    op.drop_index("ix_credentials_subject_id", table_name="credentials")
    op.drop_table("credentials")
    op.drop_index("ix_credential_requests_status", table_name="credential_requests")
    op.drop_index("ix_credential_requests_subject_id", table_name="credential_requests")
    op.drop_table("credential_requests")
    op.drop_index("ix_credential_policies_status", table_name="credential_policies")
    op.drop_index("ix_credential_policies_policy_id", table_name="credential_policies")
    op.drop_table("credential_policies")
