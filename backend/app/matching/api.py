from datetime import UTC, datetime
from typing import cast

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.authorization.schemas import Role
from app.extraction.auth import DevelopmentActor, get_development_actor, require_reviewer
from app.matching.errors import (
    ExtractionProfileNotAcceptedError,
    PreliminaryMatchAccessDeniedError,
    RoleProfileNotActiveError,
    SupersededInputError,
)
from app.matching.repository import PreliminaryMatchRepository
from app.matching.schemas import PreliminaryMatch
from app.matching.service import PreliminaryMatchService
from app.shared.errors import APIError

router = APIRouter(tags=["preliminary-matching"])


class CreatePreliminaryMatchRequest(BaseModel):
    """Only approved profile identifiers may enter preliminary matching."""

    model_config = ConfigDict(extra="forbid", strict=True)

    cv_profile_id: str = Field(min_length=1)
    role_profile_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)


class ReviewPreliminaryMatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    approved_gap_ids: list[str]
    expected_version: int = Field(ge=1)


def _service(request: Request) -> PreliminaryMatchService:
    service = getattr(request.app.state, "preliminary_match_service", None)
    if service is None:
        raise APIError(
            503, "preliminary_matching_unavailable", "Preliminary matching is not ready."
        )
    return cast(PreliminaryMatchService, service)


def _repository(request: Request) -> PreliminaryMatchRepository:
    repository = getattr(request.app.state, "preliminary_match_repository", None)
    if repository is None:
        raise APIError(
            503, "preliminary_matching_unavailable", "Preliminary matching is not ready."
        )
    return cast(PreliminaryMatchRepository, repository)


def _can_read(actor: DevelopmentActor, match: PreliminaryMatch) -> bool:
    return actor.actor_id == match.actor_id or Role.REVIEWER in actor.roles


@router.post(
    "/preliminary-matches",
    response_model=PreliminaryMatch,
    status_code=status.HTTP_201_CREATED,
)
async def create_preliminary_match(
    body: CreatePreliminaryMatchRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> PreliminaryMatch:
    try:
        return await _service(request).create(
            body.cv_profile_id,
            body.role_profile_id,
            actor.actor_id,
            body.correlation_id,
        )
    except ExtractionProfileNotAcceptedError as exc:
        raise APIError(
            409,
            "preliminary_match_input_not_accepted",
            "Preliminary matching requires accepted extraction profiles.",
        ) from exc
    except RoleProfileNotActiveError as exc:
        raise APIError(
            409,
            "role_profile_not_active",
            "Preliminary matching requires an active role profile.",
        ) from exc
    except SupersededInputError as exc:
        raise APIError(
            409,
            "preliminary_match_input_superseded",
            "Preliminary matching requires current extraction profile versions.",
        ) from exc
    except PreliminaryMatchAccessDeniedError as exc:
        raise APIError(
            403,
            "preliminary_match_access_denied",
            "Preliminary match access is denied.",
        ) from exc


@router.get("/preliminary-matches/{match_id}", response_model=PreliminaryMatch)
async def get_preliminary_match(
    match_id: str,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> PreliminaryMatch:
    match = await _repository(request).get(match_id)
    if match is None:
        raise APIError(404, "preliminary_match_not_found", "Preliminary match was not found.")
    if not _can_read(actor, match):
        raise APIError(
            403, "preliminary_match_access_denied", "Preliminary match access is denied."
        )
    return match


@router.post("/preliminary-matches/{match_id}/review", response_model=PreliminaryMatch)
async def review_preliminary_match(
    match_id: str,
    body: ReviewPreliminaryMatchRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> PreliminaryMatch:
    require_reviewer(actor)
    try:
        return await _service(request).review(
            match_id,
            actor=actor,
            approved_gap_ids=body.approved_gap_ids,
            expected_version=body.expected_version,
            reviewed_at=datetime.now(UTC),
        )
    except KeyError as exc:
        raise APIError(
            404, "preliminary_match_not_found", "Preliminary match was not found."
        ) from exc
    except PermissionError as exc:
        raise APIError(403, str(exc), "Preliminary match review is not authorized.") from exc
    except ValueError as exc:
        code = str(exc)
        raise APIError(409, code, "Preliminary match review was rejected.") from exc
