from typing import cast
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Request, status

from app.extraction.auth import DevelopmentActor, get_development_actor
from app.matching.schemas import RoleRequirement
from app.role_profile_authoring.errors import (
    RoleProfileDraftAccessDeniedError,
    RoleProfileDraftSourceError,
    RoleProfileDraftStateError,
    RoleProfileDraftVersionConflictError,
)
from app.role_profile_authoring.schemas import (
    ApproveRoleProfileDraftRequest,
    AuthorRoleProfileDraftRequest,
    CreateRoleProfileDraftRequest,
    RoleProfileDraft,
    RoleProfileDraftResponse,
    ValidateRoleProfileDraftRequest,
)
from app.role_profile_authoring.service import RoleProfileAuthoringService
from app.shared.errors import APIError

router = APIRouter(tags=["role-profile-authoring"])
logger = structlog.get_logger(__name__)


def _service(request: Request) -> RoleProfileAuthoringService:
    service = getattr(request.app.state, "role_profile_authoring_service", None)
    if service is None:
        raise APIError(
            503, "role_profile_authoring_unavailable", "Role profile authoring is not ready."
        )
    return cast(RoleProfileAuthoringService, service)


def _map_error(error: Exception) -> APIError:
    if isinstance(error, KeyError):
        return APIError(404, "role_profile_draft_not_found", "Role profile draft was not found.")
    if isinstance(error, RoleProfileDraftAccessDeniedError):
        return APIError(
            403, "role_profile_draft_access_denied", "Role profile draft access is denied."
        )
    if isinstance(error, RoleProfileDraftSourceError):
        return APIError(
            409, "role_profile_draft_source_not_accepted", "JD source is not accepted or current."
        )
    if isinstance(error, RoleProfileDraftVersionConflictError):
        return APIError(
            409, "role_profile_draft_version_conflict", "Role profile draft version is stale."
        )
    if isinstance(error, RoleProfileDraftStateError):
        return APIError(
            409, "role_profile_draft_invalid_state", "Role profile draft transition is not allowed."
        )
    return APIError(500, "role_profile_draft_failed", "Role profile draft operation failed.")


def _safe_exception_context(error: Exception) -> dict[str, object]:
    """Return diagnostic DB metadata without logging SQL or bound values."""
    original = getattr(error, "orig", None)
    diagnostic = getattr(original, "diag", None)
    return {
        "database_exception_type": type(original).__name__ if original is not None else None,
        "sqlstate": getattr(original, "sqlstate", None)
        or getattr(original, "pgcode", None),
        "constraint_name": getattr(diagnostic, "constraint_name", None),
        "table_name": getattr(diagnostic, "table_name", None),
        "column_name": getattr(diagnostic, "column_name", None),
    }


@router.get(
    "/role-profile-drafts",
    response_model=list[RoleProfileDraftResponse],
    response_model_exclude_none=True,
)
async def list_drafts(
    request: Request,
    role_id: UUID | None = None,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> list[RoleProfileDraftResponse]:
    try:
        return [_response(item, False) for item in await _service(request).list_drafts(actor, role_id)]
    except Exception as error:
        raise _map_error(error) from error


@router.post(
    "/role-profile-drafts",
    response_model=RoleProfileDraftResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_draft(
    body: CreateRoleProfileDraftRequest,
    request: Request,
    include_requirement_findings: bool = False,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> RoleProfileDraftResponse:
    try:
        return _response(
            await _service(request).create(
                actor,
                body.source_jd_profile_id,
                body.correlation_id,
                body.role_id,
                body.role_jd_version_id,
            ),
            include_requirement_findings,
        )
    except Exception as error:
        logger.exception(
            "role_profile_draft_create_failed",
            correlation_id=body.correlation_id,
            jd_profile_id=body.source_jd_profile_id,
            exception_type=type(error).__name__,
            **_safe_exception_context(error),
        )
        raise _map_error(error) from error


@router.get(
    "/role-profile-drafts/{draft_id}",
    response_model=RoleProfileDraftResponse,
    response_model_exclude_none=True,
)
async def get_draft(
    draft_id: str,
    request: Request,
    include_requirement_findings: bool = False,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> RoleProfileDraftResponse:
    try:
        return _response(await _service(request).get(actor, draft_id), include_requirement_findings)
    except KeyError as error:
        raise APIError(
            404, "role_profile_draft_not_found", "Role profile draft was not found."
        ) from error
    except Exception as error:
        raise _map_error(error) from error


@router.patch(
    "/role-profile-drafts/{draft_id}",
    response_model=RoleProfileDraftResponse,
    response_model_exclude_none=True,
)
async def author_draft(
    draft_id: str,
    body: AuthorRoleProfileDraftRequest,
    request: Request,
    include_requirement_findings: bool = False,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> RoleProfileDraftResponse:
    try:
        return _response(
            await _service(request).author(
                actor,
                draft_id,
                body.expected_version,
                body.title,
                [RoleRequirement.model_validate(item, strict=False) for item in body.requirements],
            ),
            include_requirement_findings,
        )
    except Exception as error:
        raise _map_error(error) from error


@router.post(
    "/role-profile-drafts/{draft_id}/validate",
    response_model=RoleProfileDraftResponse,
    response_model_exclude_none=True,
)
async def validate_draft(
    draft_id: str,
    body: ValidateRoleProfileDraftRequest,
    request: Request,
    include_requirement_findings: bool = False,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> RoleProfileDraftResponse:
    try:
        return _response(
            await _service(request).validate(actor, draft_id, body.expected_version),
            include_requirement_findings,
        )
    except Exception as error:
        raise _map_error(error) from error


@router.post(
    "/role-profile-drafts/{draft_id}/approve",
    response_model=RoleProfileDraftResponse,
    response_model_exclude_none=True,
)
async def approve_draft(
    draft_id: str,
    body: ApproveRoleProfileDraftRequest,
    request: Request,
    include_requirement_findings: bool = False,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> RoleProfileDraftResponse:
    try:
        if body.semantic_policy_ref is not None:
            approved = await _service(request).approve(
                actor,
                draft_id,
                body.expected_version,
                body.requested_status,
                body.semantic_policy,
                body.semantic_policy_ref,
            )
        else:
            approved = await _service(request).approve(
                actor,
                draft_id,
                body.expected_version,
                body.requested_status,
                body.semantic_policy,
            )
        return _response(approved, include_requirement_findings)
    except Exception as error:
        raise _map_error(error) from error


def _response(
    draft: RoleProfileDraft, include_requirement_findings: bool
) -> RoleProfileDraftResponse:
    values = draft.model_dump(mode="json")
    if not include_requirement_findings:
        values.pop("authoring_findings")
    return RoleProfileDraftResponse.model_validate(values, strict=False)
