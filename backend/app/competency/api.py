from datetime import datetime
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from app.authorization.schemas import ActorContext
from app.competency.errors import AuthorizationDeniedError, CompetencyRecordNotFoundError
from app.competency.service import CompetencyDecisionService
from app.extraction.auth import get_development_actor
from app.shared.errors import APIError

router = APIRouter(tags=["competency"])


class DecisionTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    assessment_decision_id: UUID
    expected_version: int = Field(ge=1)
    valid_until: datetime
    reassessment_due_at: datetime


def _service(request: Request) -> CompetencyDecisionService:
    service = getattr(request.app.state, "competency_decision_service", None)
    if service is None:
        raise APIError(503, "competency_service_unavailable", "Competency service is not ready.")
    return cast(CompetencyDecisionService, service)


async def _transition(
    operation: str,
    record_id: UUID,
    body: DecisionTransitionRequest,
    request: Request,
    actor: ActorContext,
) -> object:
    try:
        method = getattr(_service(request), operation)
        return await method(
            actor=actor,
            record_id=record_id,
            assessment_decision_id=body.assessment_decision_id,
            expected_version=body.expected_version,
            valid_until=body.valid_until,
            reassessment_due_at=body.reassessment_due_at,
        )
    except CompetencyRecordNotFoundError as exc:
        raise APIError(
            404, "competency_record_not_found", "Competency record was not found."
        ) from exc
    except AuthorizationDeniedError as exc:
        raise APIError(403, exc.reason_code, "Competency transition is not authorized.") from exc
    except ValueError as exc:
        raise APIError(
            409, "competency_version_conflict", "Competency transition was rejected."
        ) from exc


@router.post("/competencies/{record_id}/mark-assessed")
@router.post("/assessment-decisions/{record_id}/mark-assessed")
async def mark_assessed(
    record_id: UUID,
    body: DecisionTransitionRequest,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> object:
    return await _transition("mark_assessed", record_id, body, request, actor)


@router.post("/competencies/{record_id}/verify")
@router.post("/assessment-decisions/{record_id}/verify")
async def verify(
    record_id: UUID,
    body: DecisionTransitionRequest,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> object:
    return await _transition("verify", record_id, body, request, actor)


@router.post("/assessment-decisions/{record_id}/request-verification")
async def request_verification(
    record_id: UUID,
    body: DecisionTransitionRequest,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> object:
    return await _transition("request_verification", record_id, body, request, actor)


@router.post("/assessment-decisions/{record_id}/return-for-review")
async def return_for_review(
    record_id: UUID,
    body: DecisionTransitionRequest,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> object:
    return await _transition("return_for_review", record_id, body, request, actor)


@router.post("/competencies/{record_id}/require-reassessment")
async def require_reassessment(
    record_id: UUID,
    body: DecisionTransitionRequest,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> object:
    return await _transition("require_reassessment", record_id, body, request, actor)


@router.post("/competencies/{record_id}/revoke-verification")
async def revoke_verification(
    record_id: UUID,
    body: DecisionTransitionRequest,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> object:
    return await _transition("revoke_verification", record_id, body, request, actor)
