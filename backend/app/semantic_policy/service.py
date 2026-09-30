from app.capability_analysis.domain_packs.contracts import DomainKnowledgePack, DomainPackReference
from app.capability_analysis.domain_packs.registry import DomainPackRegistry
from app.semantic_policy.errors import (
    DomainPackNotActiveError,
    DomainPackNotFoundError,
    DomainPackVersionNotFoundError,
    SemanticPolicyNotActiveError,
    SemanticPolicyNotFoundError,
    SemanticPolicyPackIncompatibleError,
    SemanticPolicyVersionNotFoundError,
)
from app.semantic_policy.repository import SemanticPolicyRepository
from app.semantic_policy.schemas import (
    ResolvedSemanticPolicy,
    SemanticPolicy,
    SemanticPolicyRef,
    SemanticPolicyStatus,
)


class SemanticPolicyService:
    def __init__(
        self,
        repository: SemanticPolicyRepository,
        domain_pack_registry: DomainPackRegistry | None = None,
    ) -> None:
        self._repository = repository
        self._domain_pack_registry = domain_pack_registry

    async def create(self, policy: SemanticPolicy) -> SemanticPolicy:
        if policy.status is not SemanticPolicyStatus.DRAFT:
            raise ValueError("new semantic policies must start as draft")
        return await self._repository.save(policy)

    async def activate(self, policy_id: str, version: str) -> SemanticPolicy:
        policy = await self._repository.get(policy_id, version)
        if policy is None:
            raise KeyError((policy_id, version))
        if self._domain_pack_registry is not None:
            self._validate_pack(policy)
        return await self._repository.transition(policy_id, version, SemanticPolicyStatus.ACTIVE)

    async def deprecate(self, policy_id: str, version: str) -> SemanticPolicy:
        return await self._repository.transition(
            policy_id, version, SemanticPolicyStatus.DEPRECATED
        )

    def _validate_pack(self, policy: SemanticPolicy) -> None:
        registry = self._domain_pack_registry
        if registry is None:
            return
        try:
            pack = registry.resolve(
                _pack_reference(policy.domain_pack_id, policy.domain_pack_version)
            )
        except ValueError as error:
            if registry.has_pack_id(policy.domain_pack_id):
                raise DomainPackVersionNotFoundError(
                    "Semantic policy pack version is unavailable"
                ) from error
            raise DomainPackNotFoundError("Semantic policy pack is unavailable") from error
        if getattr(pack, "status", "active") != "active":
            raise DomainPackNotActiveError("Semantic policy pack is not active")
        if getattr(pack, "checksum", None) != policy.domain_pack_checksum:
            raise SemanticPolicyPackIncompatibleError(
                "Semantic policy pack is incompatible: checksum does not match"
            )


class SemanticPolicyResolver:
    def __init__(
        self,
        repository: SemanticPolicyRepository,
        domain_packs: tuple[DomainKnowledgePack, ...],
    ) -> None:
        self._repository = repository
        self._registry = DomainPackRegistry(domain_packs)

    async def resolve(
        self,
        reference: SemanticPolicyRef,
        *,
        target_id: str,
        target_type: str,
        historical_replay: bool = False,
    ) -> ResolvedSemanticPolicy:
        policy = await self._repository.get(reference.policy_id, reference.policy_version)
        if policy is None:
            if await self._repository.has_policy_id(reference.policy_id):
                raise SemanticPolicyVersionNotFoundError(
                    f"Semantic policy version {reference.policy_id}@{reference.policy_version} not found"
                )
            raise SemanticPolicyNotFoundError(
                f"Semantic policy {reference.policy_id}@{reference.policy_version} not found"
            )
        if policy.status is SemanticPolicyStatus.DRAFT or (
            policy.status is SemanticPolicyStatus.DEPRECATED and not historical_replay
        ):
            raise SemanticPolicyNotActiveError(
                f"Semantic policy {reference.policy_id}@{reference.policy_version} is not active"
            )
        try:
            pack = self._registry.resolve(
                _pack_reference(policy.domain_pack_id, policy.domain_pack_version)
            )
        except ValueError as exc:
            from app.semantic_policy.errors import (
                DomainPackNotFoundError,
                DomainPackVersionNotFoundError,
            )

            if self._registry.has_pack_id(policy.domain_pack_id):
                raise DomainPackVersionNotFoundError(
                    f"Domain pack version {policy.domain_pack_id}@{policy.domain_pack_version} was not found"
                ) from exc
            raise DomainPackNotFoundError(
                f"Domain pack {policy.domain_pack_id} was not found"
            ) from exc
        pack_status = getattr(pack, "status", "active")
        if pack_status != "active" and not historical_replay:
            raise DomainPackNotActiveError(
                f"Domain pack {policy.domain_pack_id}@{policy.domain_pack_version} is not active"
            )
        checksum = getattr(pack, "checksum", None)
        if checksum != policy.domain_pack_checksum:
            raise SemanticPolicyPackIncompatibleError(
                "Semantic policy pack is incompatible: checksum does not match the resolved domain pack"
            )
        return ResolvedSemanticPolicy(
            policy_id=policy.policy_id,
            policy_version=policy.version,
            core_version=policy.core_version,
            policy_status=policy.status,
            domain_pack_id=policy.domain_pack_id,
            domain_pack_version=policy.domain_pack_version,
            domain_pack_checksum=policy.domain_pack_checksum,
            target_id=target_id,
            target_type=target_type,
        )


def _pack_reference(pack_id: str, version: str) -> DomainPackReference:
    return DomainPackReference(pack_id=pack_id, version=version)
