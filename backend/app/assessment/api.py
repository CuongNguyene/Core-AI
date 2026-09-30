from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.assessment.repository import SqlAlchemyAssessmentRepository
from app.assessment.schemas import (
    AssessmentDecision,
    AssessmentSubmission,
    AssessmentTemplate,
    RiskClassification,
)
from app.authorization.schemas import ActorContext, Role
from app.extraction.auth import get_development_actor
from app.shared.errors import APIError

router = APIRouter(tags=["assessment"])


class SubmitAssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    template_id: UUID
    template_version: str = Field(min_length=1)
    artifact_reference: str = Field(min_length=1)
    evidence_ids: list[UUID] = Field(min_length=1)


class CreateDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    submission_id: UUID
    score_proposal_id: UUID
    review_id: UUID
    rubric_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    evidence_ids: list[UUID] = Field(min_length=1)
    risk_classification: RiskClassification


def _repository(request: Request) -> SqlAlchemyAssessmentRepository:
    repository = getattr(request.app.state, "assessment_repository", None)
    if repository is None:
        raise APIError(503, "assessment_repository_unavailable", "Assessment service is not ready.")
    return cast(SqlAlchemyAssessmentRepository, repository)


@router.post(
    "/assessment-templates", response_model=AssessmentTemplate, status_code=status.HTTP_201_CREATED
)
async def create_assessment_template(
    template: AssessmentTemplate,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> AssessmentTemplate:
    if Role.SME not in actor.roles and Role.ADMIN not in actor.roles:
        raise APIError(
            403, "assessment_template_forbidden", "Assessment template management is denied."
        )
    await _repository(request).save_template(template)
    return template


@router.get("/assessment-templates/{template_id}", response_model=AssessmentTemplate)
async def get_assessment_template(
    template_id: UUID,
    version: str,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> AssessmentTemplate:
    template = await _repository(request).get_template(template_id, version)
    if template is None:
        raise APIError(404, "assessment_template_not_found", "Assessment template was not found.")
    return template


@router.post(
    "/assessment-submissions",
    response_model=AssessmentSubmission,
    status_code=status.HTTP_201_CREATED,
)
async def submit_assessment(
    body: SubmitAssessmentRequest,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> AssessmentSubmission:
    submission = AssessmentSubmission(
        id=uuid4(),
        template_id=body.template_id,
        template_version=body.template_version,
        subject_id=actor.actor_id,
        artifact_reference=body.artifact_reference,
        evidence_ids=body.evidence_ids,
    )
    await _repository(request).submit(submission)
    return submission


@router.get("/assessment-submissions/{submission_id}", response_model=AssessmentSubmission)
async def get_assessment_submission(
    submission_id: UUID,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> AssessmentSubmission:
    submission = await _repository(request).get_submission(submission_id)
    if submission is None:
        raise APIError(
            404, "assessment_submission_not_found", "Assessment submission was not found."
        )
    if (
        submission.subject_id != actor.actor_id
        and Role.SME not in actor.roles
        and Role.ADMIN not in actor.roles
    ):
        raise APIError(
            403, "assessment_submission_access_denied", "Assessment submission access is denied."
        )
    return submission


@router.post(
    "/assessment-decisions", response_model=AssessmentDecision, status_code=status.HTTP_201_CREATED
)
async def create_assessment_decision(
    body: CreateDecisionRequest,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> AssessmentDecision:
    if Role.SME not in actor.roles:
        raise APIError(403, "sme_role_required", "SME role is required.")
    decision = AssessmentDecision(
        id=uuid4(),
        submission_id=body.submission_id,
        score_proposal_id=body.score_proposal_id,
        review_id=body.review_id,
        assessor_id=actor.actor_id,
        rubric_version=body.rubric_version,
        policy_version=body.policy_version,
        evidence_ids=body.evidence_ids,
        risk_classification=body.risk_classification,
        decided_at=datetime.now(UTC),
    )
    await _repository(request).create_decision(decision)
    return decision
