"""Persist assessment artifacts and competency decision history.

Revision ID: 20260803_11
Revises: 20260803_10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_11"
down_revision: str | Sequence[str] | None = "20260803_10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assessment_rubrics",
        sa.Column("record_id", sa.Uuid(), primary_key=True),
        sa.Column("rubric_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("criteria", sa.JSON(), nullable=False),
        sa.UniqueConstraint("rubric_id", "version", name="uq_assessment_rubric_version"),
    )
    op.create_table(
        "assessment_templates",
        sa.Column("record_id", sa.Uuid(), primary_key=True),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("competency_id", sa.String(128), nullable=False),
        sa.Column("rubric_id", sa.Uuid(), nullable=False),
        sa.Column("rubric_version", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("risk_classification", sa.String(16), nullable=False),
        sa.Column("validity_days", sa.Integer(), nullable=False),
        sa.Column("reassessment_lead_days", sa.Integer(), nullable=False),
        sa.UniqueConstraint("template_id", "version", name="uq_assessment_template_version"),
    )
    op.create_index("ix_assessment_templates_template_id", "assessment_templates", ["template_id"])
    op.create_index(
        "ix_assessment_templates_competency_id", "assessment_templates", ["competency_id"]
    )
    op.create_table(
        "assessment_tasks",
        sa.Column("record_id", sa.Uuid(), primary_key=True),
        sa.Column("template_record_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.String(128), nullable=False),
        sa.Column("task_type", sa.String(16), nullable=False),
        sa.Column("prompt_reference", sa.String(512), nullable=False),
        sa.ForeignKeyConstraint(["template_record_id"], ["assessment_templates.record_id"]),
        sa.UniqueConstraint("template_record_id", "task_id", name="uq_assessment_task"),
    )
    op.create_index(
        "ix_assessment_tasks_template_record_id", "assessment_tasks", ["template_record_id"]
    )
    op.create_table(
        "assessment_submissions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("template_version", sa.String(64), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_reference", sa.String(512), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_assessment_submissions_template_id", "assessment_submissions", ["template_id"]
    )
    op.create_index(
        "ix_assessment_submissions_subject_id", "assessment_submissions", ["subject_id"]
    )
    op.create_table(
        "assessment_score_proposals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("rubric_id", sa.Uuid(), nullable=False),
        sa.Column("rubric_version", sa.String(64), nullable=False),
        sa.Column("criterion_scores", sa.JSON(), nullable=False),
        sa.Column("human_review_required", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["assessment_submissions.id"]),
    )
    op.create_index(
        "ix_assessment_score_proposals_submission_id",
        "assessment_score_proposals",
        ["submission_id"],
    )
    op.create_table(
        "assessment_sme_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("score_proposal_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), nullable=False),
        sa.Column("rubric_version", sa.String(64), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("decision_rationale_reference", sa.String(512), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["assessment_submissions.id"]),
        sa.ForeignKeyConstraint(["score_proposal_id"], ["assessment_score_proposals.id"]),
    )
    op.create_index(
        "ix_assessment_sme_reviews_submission_id", "assessment_sme_reviews", ["submission_id"]
    )
    op.create_index(
        "ix_assessment_sme_reviews_score_proposal_id",
        "assessment_sme_reviews",
        ["score_proposal_id"],
    )
    op.create_table(
        "assessment_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("score_proposal_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("assessor_id", sa.Uuid(), nullable=False),
        sa.Column("rubric_version", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("risk_classification", sa.String(16), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["assessment_submissions.id"]),
        sa.ForeignKeyConstraint(["score_proposal_id"], ["assessment_score_proposals.id"]),
        sa.ForeignKeyConstraint(["review_id"], ["assessment_sme_reviews.id"]),
    )
    op.create_table(
        "assessment_audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("assessment_decision_id", sa.Uuid()),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["assessment_decision_id"], ["assessment_decisions.id"]),
    )
    op.create_index(
        "ix_assessment_audit_events_assessment_decision_id",
        "assessment_audit_events",
        ["assessment_decision_id"],
    )
    op.create_table(
        "competency_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("competency_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("level", sa.Integer()),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("last_decision_id", sa.Uuid()),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("reassessment_due_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "subject_id", "organization_id", "competency_id", name="uq_competency_subject_org"
        ),
    )
    op.create_index("ix_competency_records_subject_id", "competency_records", ["subject_id"])
    op.create_index(
        "ix_competency_records_organization_id", "competency_records", ["organization_id"]
    )
    op.create_index("ix_competency_records_competency_id", "competency_records", ["competency_id"])
    op.create_index("ix_competency_records_status", "competency_records", ["status"])
    op.create_table(
        "competency_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("competency_record_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_submission_id", sa.Uuid(), nullable=False),
        sa.Column("previous_status", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("rubric_version", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("decided_by", sa.Uuid(), nullable=False),
        sa.Column("delegation_id", sa.Uuid()),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reassessment_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["competency_record_id"], ["competency_records.id"]),
    )
    op.create_index(
        "ix_competency_decisions_competency_record_id",
        "competency_decisions",
        ["competency_record_id"],
    )
    op.create_table(
        "competency_audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("competency_record_id", sa.Uuid(), nullable=False),
        sa.Column("competency_decision_id", sa.Uuid()),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["competency_record_id"], ["competency_records.id"]),
        sa.ForeignKeyConstraint(["competency_decision_id"], ["competency_decisions.id"]),
    )
    op.create_index(
        "ix_competency_audit_events_competency_record_id",
        "competency_audit_events",
        ["competency_record_id"],
    )
    op.create_index(
        "ix_competency_audit_events_competency_decision_id",
        "competency_audit_events",
        ["competency_decision_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_competency_audit_events_competency_decision_id", table_name="competency_audit_events"
    )
    op.drop_index(
        "ix_competency_audit_events_competency_record_id", table_name="competency_audit_events"
    )
    op.drop_table("competency_audit_events")
    op.drop_index("ix_competency_decisions_competency_record_id", table_name="competency_decisions")
    op.drop_table("competency_decisions")
    op.drop_index("ix_competency_records_status", table_name="competency_records")
    op.drop_index("ix_competency_records_competency_id", table_name="competency_records")
    op.drop_index("ix_competency_records_organization_id", table_name="competency_records")
    op.drop_index("ix_competency_records_subject_id", table_name="competency_records")
    op.drop_table("competency_records")
    op.drop_index(
        "ix_assessment_audit_events_assessment_decision_id", table_name="assessment_audit_events"
    )
    op.drop_table("assessment_audit_events")
    op.drop_table("assessment_decisions")
    op.drop_index(
        "ix_assessment_sme_reviews_score_proposal_id", table_name="assessment_sme_reviews"
    )
    op.drop_index("ix_assessment_sme_reviews_submission_id", table_name="assessment_sme_reviews")
    op.drop_table("assessment_sme_reviews")
    op.drop_index(
        "ix_assessment_score_proposals_submission_id", table_name="assessment_score_proposals"
    )
    op.drop_table("assessment_score_proposals")
    op.drop_index("ix_assessment_submissions_subject_id", table_name="assessment_submissions")
    op.drop_index("ix_assessment_submissions_template_id", table_name="assessment_submissions")
    op.drop_table("assessment_submissions")
    op.drop_index("ix_assessment_tasks_template_record_id", table_name="assessment_tasks")
    op.drop_table("assessment_tasks")
    op.drop_index("ix_assessment_templates_competency_id", table_name="assessment_templates")
    op.drop_index("ix_assessment_templates_template_id", table_name="assessment_templates")
    op.drop_table("assessment_templates")
    op.drop_table("assessment_rubrics")
