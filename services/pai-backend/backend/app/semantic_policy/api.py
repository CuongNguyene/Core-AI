from typing import cast

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.extraction.auth import DevelopmentActor, get_development_actor, require_reviewer
from app.matching.repository import RoleProfileRepository
from app.semantic_policy.errors import SemanticPolicyError
from app.semantic_policy.repository import SemanticPolicyRepository
from app.semantic_policy.schemas import SemanticPolicy, SemanticPolicyRef, SemanticPolicyStatus
from app.semantic_policy.service import SemanticPolicyService
from app.shared.errors import APIError

router = APIRouter(tags=["semantic-policy"])


class CreateSemanticPolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    policy_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    domain_pack_id: str = Field(min_length=1)
    domain_pack_version: str = Field(min_length=1)
    domain_pack_checksum: str = Field(min_length=1)
    description: str = Field(min_length=1)


class BindSemanticPolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    role_profile_version: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)


def _repository(request: Request) -> SemanticPolicyRepository:
    repository = getattr(request.app.state, "semantic_policy_repository", None)
    if repository is None:
        raise APIError(503, "semantic_policy_unavailable", "Semantic policy governance is not ready.")
    return cast(SemanticPolicyRepository, repository)


def _service(request: Request) -> SemanticPolicyService:
    return SemanticPolicyService(
        _repository(request),
        getattr(request.app.state, "domain_pack_registry", None),
    )


def _role_profiles(request: Request) -> RoleProfileRepository:
    repository = getattr(request.app.state, "role_profile_repository", None)
    if repository is None:
        raise APIError(503, "role_profile_unavailable", "Role profile governance is not ready.")
    return cast(RoleProfileRepository, repository)


def _map_error(error: Exception) -> APIError:
    if isinstance(error, KeyError):
        return APIError(404, "semantic_policy_not_found", "Semantic policy version was not found.")
    if isinstance(error, SemanticPolicyError):
        return APIError(409, error.code, "Semantic policy operation failed.")
    if isinstance(error, ValueError):
        return APIError(409, "semantic_policy_invalid_transition", str(error))
    return APIError(500, "semantic_policy_failed", "Semantic policy operation failed.")


@router.post("/semantic-policies", response_model=SemanticPolicy, status_code=status.HTTP_201_CREATED)
async def create_policy(
    body: CreateSemanticPolicyRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> SemanticPolicy:
    require_reviewer(actor)
    try:
        policy = await _service(request).create(
            SemanticPolicy(
                policy_id=body.policy_id,
                version=body.version,
                status=SemanticPolicyStatus.DRAFT,
                domain_pack_id=body.domain_pack_id,
                domain_pack_version=body.domain_pack_version,
                domain_pack_checksum=body.domain_pack_checksum,
                description=body.description,
                created_by=str(actor.actor_id),
            )
        )
        await _append_audit(request, "semantic_policy_created", policy, actor)
        return policy
    except Exception as error:
        raise _map_error(error) from error


@router.get(
    "/semantic-policies/{policy_id}/versions/{version}",
    response_model=SemanticPolicy,
)
async def get_policy(
    policy_id: str,
    version: str,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> SemanticPolicy:
    require_reviewer(actor)
    policy = await _repository(request).get(policy_id, version)
    if policy is None:
        raise APIError(404, "semantic_policy_not_found", "Semantic policy version was not found.")
    return policy


@router.post(
    "/semantic-policies/{policy_id}/versions/{version}/activate",
    response_model=SemanticPolicy,
)
async def activate_policy(
    policy_id: str,
    version: str,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> SemanticPolicy:
    require_reviewer(actor)
    try:
        policy = await _service(request).activate(policy_id, version)
        await _append_audit(request, "semantic_policy_activated", policy, actor)
        return policy
    except Exception as error:
        raise _map_error(error) from error


@router.post(
    "/semantic-policies/{policy_id}/versions/{version}/deprecate",
    response_model=SemanticPolicy,
)
async def deprecate_policy(
    policy_id: str,
    version: str,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> SemanticPolicy:
    require_reviewer(actor)
    try:
        policy = await _service(request).deprecate(policy_id, version)
        await _append_audit(request, "semantic_policy_deprecated", policy, actor)
        return policy
    except Exception as error:
        raise _map_error(error) from error


@router.put("/role-profiles/{role_profile_id}/semantic-policy")
async def bind_role_profile_policy(
    role_profile_id: str,
    body: BindSemanticPolicyRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> object:
    require_reviewer(actor)
    reference = SemanticPolicyRef(policy_id=body.policy_id, policy_version=body.policy_version)
    try:
        resolver = getattr(request.app.state, "semantic_policy_resolver", None)
        if resolver is None:
            raise ValueError("semantic policy resolver is unavailable")
        await resolver.resolve(
            reference,
            target_id=role_profile_id,
            target_type="role_profile",
        )
        await _role_profiles(request).bind_semantic_policy(
            role_profile_id, body.role_profile_version, reference
        )
        policy = await _repository(request).get(body.policy_id, body.policy_version)
        if policy is not None:
            await _append_audit(request, "role_semantic_policy_bound", policy, actor)
        profile = await _role_profiles(request).get_version(
            role_profile_id, body.role_profile_version
        )
        if profile is None:
            raise KeyError((role_profile_id, body.role_profile_version))
        return profile
    except KeyError as error:
        raise APIError(404, "role_profile_not_found", "Role profile version was not found.") from error
    except SemanticPolicyError as error:
        raise APIError(409, error.code, "Semantic policy binding is not valid.") from error
    except ValueError as error:
        raise APIError(409, "semantic_policy_binding_invalid", str(error)) from error


async def _append_audit(
    request: Request, action: str, policy: SemanticPolicy, actor: DevelopmentActor
) -> None:
    repository = _repository(request)
    await repository.append_audit(
        action=action,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        actor_id=str(actor.actor_id),
    )
