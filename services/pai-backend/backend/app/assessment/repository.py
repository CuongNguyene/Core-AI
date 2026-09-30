from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.assessment.models import (
    AssessmentAuditEventRecord,
    AssessmentDecisionRecord,
    AssessmentRubricRecord,
    AssessmentScoreProposalRecord,
    AssessmentSMEReviewRecord,
    AssessmentSubmissionRecord,
    AssessmentTaskRecord,
    AssessmentTemplateRecord,
)
from app.assessment.schemas import (
    AssessmentDecision,
    AssessmentSubmission,
    AssessmentTask,
    AssessmentTaskType,
    AssessmentTemplate,
    RiskClassification,
    Rubric,
    RubricCriterion,
    ScoreProposal,
    SMEReview,
)


class SqlAlchemyAssessmentRepository:
    """Owns immutable assessment artifacts and their safe audit boundary."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save_template(self, template: AssessmentTemplate) -> None:
        async with self._session_factory() as session, session.begin():
            existing = await session.scalar(
                select(AssessmentTemplateRecord).where(
                    AssessmentTemplateRecord.template_id == template.id,
                    AssessmentTemplateRecord.version == template.version,
                )
            )
            if existing is not None:
                raise ValueError("assessment_template_version_immutable")
            rubric = await session.scalar(
                select(AssessmentRubricRecord).where(
                    AssessmentRubricRecord.rubric_id == template.rubric.id,
                    AssessmentRubricRecord.version == template.rubric.version,
                )
            )
            if rubric is None:
                session.add(
                    AssessmentRubricRecord(
                        record_id=uuid4(),
                        rubric_id=template.rubric.id,
                        version=template.rubric.version,
                        criteria=[
                            item.model_dump(mode="json") for item in template.rubric.criteria
                        ],
                    )
                )
            record_id = uuid4()
            session.add(
                AssessmentTemplateRecord(
                    record_id=record_id,
                    template_id=template.id,
                    version=template.version,
                    competency_id=template.competency_id,
                    rubric_id=template.rubric.id,
                    rubric_version=template.rubric.version,
                    policy_version=template.policy_version,
                    risk_classification=template.risk_classification.value,
                    validity_days=template.validity_days,
                    reassessment_lead_days=template.reassessment_lead_days,
                )
            )
            session.add_all(
                [
                    AssessmentTaskRecord(
                        record_id=uuid4(),
                        template_record_id=record_id,
                        task_id=task.id,
                        task_type=task.task_type.value,
                        prompt_reference=task.prompt_reference,
                    )
                    for task in template.tasks
                ]
            )

    async def submit(self, submission: AssessmentSubmission) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                AssessmentSubmissionRecord(
                    id=submission.id,
                    template_id=submission.template_id,
                    template_version=submission.template_version,
                    subject_id=submission.subject_id,
                    artifact_reference=submission.artifact_reference,
                    evidence_ids=[str(item) for item in submission.evidence_ids],
                )
            )

    async def get_submission(self, submission_id: UUID) -> AssessmentSubmission | None:
        async with self._session_factory() as session:
            record = await session.get(AssessmentSubmissionRecord, submission_id)
            if record is None:
                return None
            return AssessmentSubmission(
                id=record.id,
                template_id=record.template_id,
                template_version=record.template_version,
                subject_id=record.subject_id,
                artifact_reference=record.artifact_reference,
                evidence_ids=[UUID(value) for value in record.evidence_ids],
            )

    async def get_template(self, template_id: UUID, version: str) -> AssessmentTemplate | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(AssessmentTemplateRecord).where(
                    AssessmentTemplateRecord.template_id == template_id,
                    AssessmentTemplateRecord.version == version,
                )
            )
            if record is None:
                return None
            rubric_record = await session.scalar(
                select(AssessmentRubricRecord).where(
                    AssessmentRubricRecord.rubric_id == record.rubric_id,
                    AssessmentRubricRecord.version == record.rubric_version,
                )
            )
            if rubric_record is None:
                return None
            tasks = (
                await session.scalars(
                    select(AssessmentTaskRecord).where(
                        AssessmentTaskRecord.template_record_id == record.record_id
                    )
                )
            ).all()
            return AssessmentTemplate(
                id=record.template_id,
                version=record.version,
                competency_id=record.competency_id,
                rubric=Rubric(
                    id=rubric_record.rubric_id,
                    version=rubric_record.version,
                    criteria=[
                        RubricCriterion.model_validate(item) for item in rubric_record.criteria
                    ],
                ),
                policy_version=record.policy_version,
                risk_classification=RiskClassification(record.risk_classification),
                validity_days=record.validity_days,
                reassessment_lead_days=record.reassessment_lead_days,
                tasks=[
                    AssessmentTask(
                        id=item.task_id,
                        task_type=AssessmentTaskType(item.task_type),
                        prompt_reference=item.prompt_reference,
                    )
                    for item in tasks
                ],
            )

    async def record_score_proposal(self, proposal: ScoreProposal) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                AssessmentScoreProposalRecord(
                    id=proposal.id,
                    submission_id=proposal.submission_id,
                    rubric_id=proposal.rubric_id,
                    rubric_version=proposal.rubric_version,
                    criterion_scores=proposal.criterion_scores,
                    human_review_required=proposal.human_review_required,
                )
            )

    async def record_sme_review(self, review: SMEReview) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                AssessmentSMEReviewRecord(
                    id=review.id,
                    submission_id=review.submission_id,
                    score_proposal_id=review.score_proposal_id,
                    reviewer_id=review.reviewer_id,
                    rubric_version=review.rubric_version,
                    evidence_ids=[str(item) for item in review.evidence_ids],
                    decision_rationale_reference=review.decision_rationale_reference,
                )
            )

    async def create_decision(self, decision: AssessmentDecision) -> AssessmentDecision:
        async with self._session_factory() as session, session.begin():
            session.add(
                AssessmentDecisionRecord(
                    id=decision.id,
                    submission_id=decision.submission_id,
                    score_proposal_id=decision.score_proposal_id,
                    review_id=decision.review_id,
                    assessor_id=decision.assessor_id,
                    rubric_version=decision.rubric_version,
                    policy_version=decision.policy_version,
                    evidence_ids=[str(item) for item in decision.evidence_ids],
                    risk_classification=decision.risk_classification.value,
                    decided_at=decision.decided_at,
                )
            )
            await self._append_audit(session, decision)
        return decision

    async def get_decision(self, decision_id: UUID) -> AssessmentDecision | None:
        async with self._session_factory() as session:
            record = await session.get(AssessmentDecisionRecord, decision_id)
            if record is None:
                return None
            return AssessmentDecision(
                id=record.id,
                submission_id=record.submission_id,
                score_proposal_id=record.score_proposal_id,
                review_id=record.review_id,
                assessor_id=record.assessor_id,
                rubric_version=record.rubric_version,
                policy_version=record.policy_version,
                evidence_ids=[UUID(value) for value in record.evidence_ids],
                risk_classification=record.risk_classification,
                decided_at=record.decided_at,
            )

    @staticmethod
    async def _append_audit(session: AsyncSession, decision: AssessmentDecision) -> None:
        session.add(
            AssessmentAuditEventRecord(
                id=uuid4(),
                assessment_decision_id=decision.id,
                actor_id=decision.assessor_id,
                action="ASSESSMENT_DECISION_CREATED",
                audit_metadata={
                    "submission_id": str(decision.submission_id),
                    "rubric_version": decision.rubric_version,
                    "policy_version": decision.policy_version,
                    "risk_classification": decision.risk_classification.value,
                },
            )
        )
