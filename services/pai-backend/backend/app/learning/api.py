from typing import cast

from fastapi import APIRouter, Depends, Request, status

from app.extraction.auth import DevelopmentActor, get_development_actor
from app.learning.errors import LearningPathValidationError
from app.learning.repository import LearningPathRepository
from app.learning.schemas import (
    CapabilityAnalysisLearningPathRequest,
    LearningPath,
    LearningPathLifecycleRequest,
    LearningPathRequest,
)
from app.learning.service import LearningPathService
from app.shared.errors import APIError

router = APIRouter(tags=["learning"])


def _service(request: Request) -> LearningPathService:
    service = getattr(request.app.state, "learning_path_service", None)
    if service is None:
        raise APIError(503, "learning_path_unavailable", "Learning path service is not ready.")
    return cast(LearningPathService, service)


def _repository(request: Request) -> LearningPathRepository:
    repository = getattr(request.app.state, "learning_path_repository", None)
    if repository is None:
        raise APIError(503, "learning_path_unavailable", "Learning path service is not ready.")
    return cast(LearningPathRepository, repository)


@router.post("/learning-paths", response_model=LearningPath, status_code=status.HTTP_201_CREATED)
async def create_learning_path(
    body: LearningPathRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> LearningPath:
    try:
        return await _service(request).create(actor=actor, request=body)
    except LearningPathValidationError as exc:
        code = str(exc)
        messages = {
            "subject_mismatch": "Learning path subject is not authorized.",
            "target_profile_not_active": "Target competency profile is not active.",
            "preliminary_match_not_found": "Preliminary match was not found.",
            "preliminary_match_not_reviewed": "Preliminary match is not reviewed.",
            "preliminary_match_subject_mismatch": "Preliminary match subject is not authorized.",
            "preliminary_match_target_mismatch": "Preliminary match target is stale.",
            "gap_not_approved": "The requested gap was not approved.",
            "gap_not_in_target_profile": "The requested gap is not in the target profile.",
            "gap_confidence_insufficient": "The approved gap confidence is insufficient.",
            "verified_competency_not_found": "Verified competency was not found.",
            "verified_competency_required": "A verified competency is required.",
            "verified_competency_scope_mismatch": "Verified competency scope is not authorized.",
            "verified_competency_expired": "Verified competency is not valid through the target date.",
        }
        raise APIError(
            409, code, messages.get(code, "Learning path input is not eligible.")
        ) from exc


@router.get("/learning-paths/{path_id}", response_model=LearningPath)
async def get_learning_path(
    path_id: str,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> LearningPath:
    try:
        return await _service(request).get(path_id, actor=actor)
    except LearningPathValidationError as exc:
        code = str(exc)
        status_code = 404 if code == "learning_path_not_found" else 403
        raise APIError(status_code, code, "Learning path access is denied.") from exc


@router.post("/learning-paths/{path_id}/supersede", response_model=LearningPath)
async def supersede_learning_path(
    path_id: str,
    body: LearningPathRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> LearningPath:
    try:
        return await _service(request).supersede(path_id, actor=actor, request=body)
    except LearningPathValidationError as exc:
        code = str(exc)
        status_code = (
            404
            if code == "learning_path_not_found"
            else 403
            if code == "learning_path_access_denied"
            else 409
        )
        raise APIError(status_code, code, "Learning path supersession was rejected.") from exc


@router.post("/learning-paths/{path_id}/review", response_model=LearningPath)
async def review_learning_path(
    path_id: str,
    body: LearningPathLifecycleRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> LearningPath:
    try:
        return await _service(request).review(
            path_id, actor=actor, expected_version=body.expected_version
        )
    except LearningPathValidationError as exc:
        code = str(exc)
        status_code = 404 if code == "learning_path_not_found" else 403 if code == "learning_path_access_denied" else 409
        raise APIError(status_code, code, "Learning path review was rejected.") from exc


@router.post("/learning-paths/{path_id}/approve", response_model=LearningPath)
async def approve_learning_path(
    path_id: str,
    body: LearningPathLifecycleRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> LearningPath:
    try:
        return await _service(request).approve(
            path_id, actor=actor, expected_version=body.expected_version
        )
    except LearningPathValidationError as exc:
        code = str(exc)
        status_code = 404 if code == "learning_path_not_found" else 403 if code == "learning_path_access_denied" else 409
        raise APIError(status_code, code, "Learning path approval was rejected.") from exc


@router.post("/learning-paths/{path_id}/regenerate", response_model=LearningPath)
async def regenerate_learning_path(
    path_id: str,
    body: CapabilityAnalysisLearningPathRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> LearningPath:
    try:
        return await _service(request).regenerate_from_capability_analysis(
            path_id, actor=actor, request=body
        )
    except LearningPathValidationError as exc:
        code = str(exc)
        status_code = 404 if code == "learning_path_not_found" else 403 if code == "learning_path_access_denied" else 409
        raise APIError(status_code, code, "Learning path regeneration was rejected.") from exc
