from typing import Literal, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.authorization.repository import (
    InMemoryDelegationRepository,
    SqlAlchemyDelegationRepository,
)
from app.authorization.schemas import ActorContext, DelegationStatus, Role, ScopedDelegation
from app.extraction.auth import get_development_actor
from app.shared.errors import APIError

router = APIRouter(tags=["delegations"])


class CreateDelegationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    organization_id: UUID
    permission: Literal[
        "competency.verify",
        "credential.approve",
        "credential.issue",
        "credential.revoke",
    ] = "competency.verify"
    competency_scope: list[str] = Field(min_length=1)
    valid_from: str
    valid_until: str
    reason: str = Field(min_length=1, max_length=256)


class DelegationTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=256)


def _repository(request: Request) -> InMemoryDelegationRepository | SqlAlchemyDelegationRepository:
    repository = getattr(request.app.state, "delegation_repository", None)
    if repository is None:
        raise APIError(503, "delegation_repository_unavailable", "Delegation service is not ready.")
    return cast(InMemoryDelegationRepository | SqlAlchemyDelegationRepository, repository)


def _require_admin(actor: ActorContext) -> None:
    if Role.ADMIN not in actor.roles:
        raise APIError(403, "admin_role_required", "Administrator role is required.")


@router.post("/delegations", response_model=ScopedDelegation, status_code=status.HTTP_201_CREATED)
async def create_delegation(
    body: CreateDelegationRequest,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> ScopedDelegation:
    _require_admin(actor)
    if body.user_id == actor.actor_id:
        raise APIError(403, "self_delegation_forbidden", "Self delegation is forbidden.")
    from datetime import datetime

    try:
        valid_from = datetime.fromisoformat(body.valid_from)
        valid_until = datetime.fromisoformat(body.valid_until)
    except ValueError as exc:
        raise APIError(422, "invalid_delegation_window", "Delegation validity is invalid.") from exc
    delegation = ScopedDelegation(
        id=uuid4(),
        user_id=body.user_id,
        permission=body.permission,
        organization_id=body.organization_id,
        competency_scope=frozenset(body.competency_scope),
        valid_from=valid_from,
        valid_until=valid_until,
        status=DelegationStatus.DRAFT,
        granted_by=actor.actor_id,
        reason=body.reason,
        version=1,
    )
    repository = _repository(request)
    if not hasattr(repository, "create"):
        raise APIError(503, "delegation_write_unavailable", "Delegation writes are not ready.")
    return await repository.create(delegation)


@router.get("/delegations/{delegation_id}", response_model=ScopedDelegation)
async def get_delegation(
    delegation_id: UUID,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> ScopedDelegation:
    delegation = await _repository(request).get(delegation_id)
    if delegation is None:
        raise APIError(404, "delegation_not_found", "Delegation was not found.")
    if delegation.organization_id != actor.organization_id and Role.ADMIN not in actor.roles:
        raise APIError(403, "delegation_access_denied", "Delegation access is denied.")
    return delegation


@router.get("/users/{user_id}/delegations", response_model=list[ScopedDelegation])
async def list_user_delegations(
    user_id: UUID,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> list[ScopedDelegation]:
    if user_id != actor.actor_id and Role.ADMIN not in actor.roles:
        raise APIError(403, "delegation_access_denied", "Delegation access is denied.")
    return list(await _repository(request).active_for_user(user_id))


@router.post("/delegations/{delegation_id}/{target}", response_model=ScopedDelegation)
async def transition_delegation(
    delegation_id: UUID,
    target: str,
    body: DelegationTransitionRequest,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> ScopedDelegation:
    _require_admin(actor)
    try:
        target_status = DelegationStatus(target)
    except ValueError as exc:
        raise APIError(
            404, "delegation_transition_not_found", "Delegation transition was not found."
        ) from exc
    if target_status not in {
        DelegationStatus.ACTIVE,
        DelegationStatus.SUSPENDED,
        DelegationStatus.REVOKED,
    }:
        raise APIError(422, "delegation_transition_invalid", "Delegation transition is invalid.")
    try:
        return await _repository(request).transition(
            delegation_id,
            actor.actor_id,
            expected_version=body.expected_version,
            target=target_status,
            reason=body.reason,
        )
    except (KeyError, ValueError) as exc:
        raise APIError(
            409, "delegation_transition_conflict", "Delegation transition was rejected."
        ) from exc
