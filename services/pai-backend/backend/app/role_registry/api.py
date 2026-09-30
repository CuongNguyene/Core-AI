from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from app.extraction.auth import DevelopmentActor, get_development_actor, require_reviewer
from app.matching.repository import RoleProfileRepository
from app.matching.schemas import (
    ActivateRoleCompetencyProfileRequest,
    RoleCompetencyProfile,
    RoleCompetencyProfileHistoryEntry,
)
from app.role_registry.schemas import (
    CreateRoleRequest,
    Role,
    RoleJDVersion,
    RoleSummary,
    UpdateRoleRequest,
)
from app.role_registry.service import RoleRegistryService
from app.shared.errors import APIError

router = APIRouter(prefix="/roles", tags=["role-registry"])


def _service(request: Request) -> RoleRegistryService:
    service = getattr(request.app.state, "role_registry_service", None)
    if service is None:
        raise APIError(503, "role_registry_unavailable", "Role registry is not ready.")
    return cast(RoleRegistryService, service)


@router.post("", response_model=Role, status_code=status.HTTP_201_CREATED)
async def create_role(
    body: CreateRoleRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> Role:
    return await _service(request).create_role(actor.organization_id, actor.actor_id, body)


@router.get("", response_model=list[RoleSummary])
async def search_roles(request: Request, q: str | None = None, actor: DevelopmentActor = Depends(get_development_actor)) -> list[RoleSummary]:
    return await _service(request).search_roles(actor.organization_id, q)


@router.get("/{role_id}", response_model=Role)
async def get_role(
    role_id: UUID,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> Role:
    try:
        return await _service(request).get_role(actor.organization_id, role_id)
    except KeyError as exc:
        raise APIError(404, "role_not_found", "Role was not found.") from exc


@router.patch("/{role_id}", response_model=Role)
async def update_role(
    role_id: UUID,
    body: UpdateRoleRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> Role:
    try:
        return await _service(request).update_role(actor.organization_id, role_id, body)
    except KeyError as exc:
        raise APIError(404, "role_not_found", "Role was not found.") from exc


@router.post("/{role_id}/jd/versions", response_model=RoleJDVersion, status_code=status.HTTP_201_CREATED)
async def attach_jd_version(
    role_id: UUID,
    document_id: UUID,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> RoleJDVersion:
    try:
        document = await request.app.state.document_repository.get(document_id)
        if document is None:
            raise APIError(404, "document_not_found", "JD document was not found.")
        if document.organization_id != actor.organization_id:
            raise APIError(403, "role_registry_access_denied", "Document is outside actor organization.")
        return await _service(request).attach_document_as_jd_version(role_id, document)
    except APIError:
        raise
    except PermissionError as exc:
        raise APIError(403, "role_registry_access_denied", str(exc)) from exc
    except ValueError as exc:
        raise APIError(409, "role_jd_version_invalid", str(exc)) from exc


@router.get("/{role_id}/jd/versions", response_model=list[RoleJDVersion])
async def list_jd_versions(
    role_id: UUID,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> list[RoleJDVersion]:
    try:
        return await _service(request).list_jd_versions(role_id, actor.organization_id)
    except KeyError as exc:
        raise APIError(404, "role_not_found", "Role was not found.") from exc


@router.get(
    "/{role_id}/competency-profiles",
    response_model=list[RoleCompetencyProfileHistoryEntry],
)
async def list_competency_profiles(
    role_id: UUID,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> list[RoleCompetencyProfileHistoryEntry]:
    try:
        repository = cast(
            RoleProfileRepository,
            getattr(request.app.state, "role_profile_repository", None),
        )
        if repository is None:
            raise APIError(
                503, "role_profile_unavailable", "Role profile repository is not ready."
            )
        role = await _service(request).get_role(actor.organization_id, role_id)
        profiles = await repository.list_for_role(role_id)
        return [
            RoleCompetencyProfileHistoryEntry(
                profile_id=profile.id,
                profile_version=profile.version,
                governance_version=profile.governance_version,
                status=profile.status,
                is_active=role.active_role_profile_id == profile.id,
                role_jd_version_id=profile.role_jd_version_id,
            )
            for profile in profiles
        ]
    except APIError:
        raise
    except KeyError as exc:
        raise APIError(404, "role_not_found", "Role was not found.") from exc


@router.get(
    "/{role_id}/competency-profiles/active",
    response_model=RoleCompetencyProfile,
)
async def get_active_competency_profile(
    role_id: UUID,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> RoleCompetencyProfile:
    try:
        await _service(request).get_role(actor.organization_id, role_id)
        repository = cast(
            RoleProfileRepository,
            getattr(request.app.state, "role_profile_repository", None),
        )
        if repository is None:
            raise APIError(
                503, "role_profile_unavailable", "Role profile repository is not ready."
            )
        profile = await repository.get_active_for_role(role_id)
        if profile is None:
            raise APIError(404, "active_role_profile_not_found", "No active role profile exists.")
        return profile
    except APIError:
        raise
    except KeyError as exc:
        raise APIError(404, "role_not_found", "Role was not found.") from exc


@router.post(
    "/{role_id}/competency-profiles/{profile_id}/activate",
    response_model=RoleCompetencyProfile,
)
async def activate_competency_profile(
    role_id: UUID,
    profile_id: str,
    body: ActivateRoleCompetencyProfileRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> RoleCompetencyProfile:
    require_reviewer(actor)
    try:
        await _service(request).get_role(actor.organization_id, role_id)
        repository = cast(
            RoleProfileRepository,
            getattr(request.app.state, "role_profile_repository", None),
        )
        if repository is None:
            raise APIError(
                503, "role_profile_unavailable", "Role profile repository is not ready."
            )
        return await repository.activate_for_role(
            role_id,
            profile_id=profile_id,
            governance_version=body.governance_version,
        )
    except APIError:
        raise
    except KeyError as exc:
        raise APIError(404, "role_profile_not_found", "Exact role profile was not found.") from exc
    except ValueError as exc:
        code = "role_profile_activation_rejected"
        if "older governance version" in str(exc):
            code = "role_profile_activation_regression"
        raise APIError(409, code, str(exc)) from exc
