from uuid import UUID

from app.authorization.schemas import ActorContext, Role
from app.matching.schemas import (
    RoleProfileSemanticPolicy,
    RoleProfileStatus,
    RoleRequirement,
)
from app.role_profile_authoring.errors import (
    RoleProfileDraftAccessDeniedError,
)
from app.role_profile_authoring.repository import RoleProfileDraftRepository
from app.role_profile_authoring.schemas import RoleProfileDraft
from app.semantic_policy.schemas import SemanticPolicyRef


class RoleProfileAuthoringService:
    def __init__(self, repository: RoleProfileDraftRepository) -> None:
        self._repository = repository

    async def create(
        self,
        actor: ActorContext,
        source_jd_profile_id: str,
        correlation_id: str,
        role_id: UUID | None = None,
        role_jd_version_id: UUID | None = None,
    ) -> RoleProfileDraft:
        self._require_reviewer(actor)
        return await self._repository.create_from_jd(
            source_jd_profile_id,
            actor.actor_id,
            actor.organization_id,
            correlation_id,
            role_id,
            role_jd_version_id,
        )

    async def get(self, actor: ActorContext, draft_id: str) -> RoleProfileDraft:
        draft = await self._repository.get(draft_id)
        if draft is None:
            raise KeyError(draft_id)
        self._require_scope(actor, draft)
        return draft

    async def list_drafts(
        self, actor: ActorContext, role_id: UUID | None = None
    ) -> list[RoleProfileDraft]:
        drafts = await self._repository.list_for_organization(actor.organization_id)
        if role_id is None:
            return drafts
        return [draft for draft in drafts if draft.role_id == role_id]

    async def author(
        self,
        actor: ActorContext,
        draft_id: str,
        expected_version: int,
        title: str | None,
        requirements: list[RoleRequirement],
    ) -> RoleProfileDraft:
        self._require_reviewer(actor)
        draft = await self.get(actor, draft_id)
        return await self._repository.author(
            draft.id,
            expected_version=expected_version,
            actor_id=actor.actor_id,
            title=title,
            requirements=requirements,
        )

    async def validate(
        self, actor: ActorContext, draft_id: str, expected_version: int
    ) -> RoleProfileDraft:
        self._require_reviewer(actor)
        draft = await self.get(actor, draft_id)
        return await self._repository.validate(
            draft.id, expected_version=expected_version, actor_id=actor.actor_id
        )

    async def approve(
        self,
        actor: ActorContext,
        draft_id: str,
        expected_version: int,
        requested_status: RoleProfileStatus,
        semantic_policy: RoleProfileSemanticPolicy,
        semantic_policy_ref: SemanticPolicyRef | None = None,
    ) -> RoleProfileDraft:
        self._require_reviewer(actor)
        draft = await self.get(actor, draft_id)
        if semantic_policy_ref is not None:
            return await self._repository.approve(
                draft.id,
                expected_version=expected_version,
                actor_id=actor.actor_id,
                requested_status=requested_status,
                semantic_policy=semantic_policy,
                semantic_policy_ref=semantic_policy_ref,
            )
        return await self._repository.approve(
            draft.id,
            expected_version=expected_version,
            actor_id=actor.actor_id,
            requested_status=requested_status,
            semantic_policy=semantic_policy,
        )

    @staticmethod
    def _require_reviewer(actor: ActorContext) -> None:
        if Role.REVIEWER not in actor.roles:
            raise RoleProfileDraftAccessDeniedError("reviewer role required")

    @staticmethod
    def _require_scope(actor: ActorContext, draft: RoleProfileDraft) -> None:
        if actor.organization_id != draft.organization_id:
            raise RoleProfileDraftAccessDeniedError("organization scope mismatch")
        if Role.REVIEWER not in actor.roles and actor.actor_id != draft.owner_actor_id:
            raise RoleProfileDraftAccessDeniedError("draft access denied")
